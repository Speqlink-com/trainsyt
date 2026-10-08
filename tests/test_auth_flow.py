"""End-to-end tests for the cookie-based authentication lifecycle."""

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete, func
from sqlmodel import select

from app.core.core import settings
from app.core.database import async_session
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.users import User
from app.scripts.seed_admin import seed_admin
from app.services.email_service import email_service
from main import app


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]}


async def login(client: AsyncClient, email: str, password: str):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def test_seed_admin_is_idempotent_and_can_login(client: AsyncClient) -> None:
    async with async_session() as db:
        assert await seed_admin(db) is False
        count = await db.scalar(select(func.count()).select_from(User))
    assert count == 1

    response = await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["user"]["role"] == UserRole.SUPER_ADMIN.value
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")
    assert client.cookies.get(settings.CSRF_COOKIE_NAME)


async def test_seed_admin_temporary_password_requires_immediate_change(
    client: AsyncClient,
    monkeypatch,
) -> None:
    async with async_session() as db:
        await db.execute(delete(User))
        await db.commit()

    monkeypatch.setattr(settings, "SEED_ADMIN_EMAIL", "comsiwende@gmail.com")
    monkeypatch.setattr(settings, "SEED_ADMIN_PASSWORD", SecretStr("Admin123"))
    monkeypatch.setattr(settings, "SEED_ADMIN_FIRST_NAME", "Comfortine")
    monkeypatch.setattr(settings, "SEED_ADMIN_LAST_NAME", "Siwende")
    monkeypatch.setattr(settings, "SEED_ADMIN_FORCE_PASSWORD_CHANGE", True)

    async with async_session() as db:
        assert await seed_admin(db) is True
        seeded = await db.scalar(
            select(User).where(User.email == "comsiwende@gmail.com")
        )
    assert seeded
    assert seeded.role == UserRole.SUPER_ADMIN
    assert seeded.is_password_changed is False
    assert seeded.last_password_change_at is None

    first_login = await login(client, "comsiwende@gmail.com", "Admin123")
    assert first_login.status_code == 200
    assert first_login.json()["data"]["password_change_required"] is True
    assert client.cookies.get("temp_token")
    assert client.cookies.get("access_token") is None

    changed = await client.post(
        "/api/auth/first-time-password-change",
        headers=csrf_headers(client),
        json={
            "new_password": "ProductionAdmin123!",
            "confirm_password": "ProductionAdmin123!",
        },
    )
    assert changed.status_code == 200, changed.text
    assert client.cookies.get("temp_token") is None
    assert client.cookies.get("access_token")


async def test_at_most_six_active_administrator_accounts(
    client: AsyncClient,
    monkeypatch,
) -> None:
    async def accept_invitation(**_: str) -> bool:
        return True

    monkeypatch.setattr(email_service, "send_temporary_password", accept_invitation)
    admin_login = await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    assert admin_login.status_code == 200

    password_hash = hash_password("AdminLimit123!")
    administrators: list[User] = []
    async with async_session() as db:
        for index in range(5):
            administrator = User(
                email=f"administrator-{index}@example.com",
                hashed_password=password_hash,
                first_name="Limit",
                last_name=f"Admin {index}",
                role=UserRole.ADMIN,
                employee_id=f"ADM-{index}",
                phone_number=f"+2547000010{index:02d}",
                is_active=True,
                is_password_changed=True,
                is_email_verified=True,
            )
            db.add(administrator)
            administrators.append(administrator)
        await db.commit()
        for administrator in administrators:
            await db.refresh(administrator)

    rejected = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "seventh-admin@example.com",
            "first_name": "Seventh",
            "last_name": "Administrator",
            "role": "admin",
            "phone_number": "+254700001099",
            "employee_id": "ADM-099",
        },
    )
    assert rejected.status_code == 409
    assert "maximum of 6" in rejected.json()["detail"].lower()

    deactivated = await client.patch(
        f"/api/auth/users/{administrators[0].id}/status",
        headers=csrf_headers(client),
        json={"is_active": False},
    )
    assert deactivated.status_code == 200

    created = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "replacement-admin@example.com",
            "first_name": "Replacement",
            "last_name": "Administrator",
            "role": "admin",
            "phone_number": "+254700001098",
            "employee_id": "ADM-098",
        },
    )
    assert created.status_code == 201, created.text


async def test_invitation_first_login_rotation_replay_and_admin_control(
    client: AsyncClient,
    monkeypatch,
) -> None:
    delivered: dict[str, str] = {}

    async def capture_invitation(**kwargs: str) -> bool:
        delivered.update(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_temporary_password", capture_invitation)
    admin_login = await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    assert admin_login.status_code == 200, admin_login.text

    invitation = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "trainer@example.com",
            "first_name": "Training",
            "last_name": "Lead",
            "role": "trainer",
            "phone_number": "0700 000 010",
            "employee_id": "TR-001",
            "department": "Learning",
        },
    )
    assert invitation.status_code == 201
    assert invitation.json()["data"]["invitation_sent"] is True
    invited_user = invitation.json()["data"]["user"]
    assert delivered["email"] == "trainer@example.com"
    assert delivered["temporary_password"]

    duplicate_phone = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "another@example.com",
            "first_name": "Another",
            "last_name": "Trainer",
            "role": "trainer",
            "phone_number": "+254700000010",
            "employee_id": "TR-002",
        },
    )
    assert duplicate_phone.status_code == 409
    assert "phone number" in duplicate_phone.json()["detail"].lower()

    duplicate_identifier = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "third@example.com",
            "first_name": "Third",
            "last_name": "Trainer",
            "role": "trainer",
            "phone_number": "+254700000011",
            "employee_id": "tr-001",
        },
    )
    assert duplicate_identifier.status_code == 409
    assert "code" in duplicate_identifier.json()["detail"].lower()

    listing = await client.get("/api/auth/users", params={"role": "trainer"})
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as trainer_client:
        first_login = await login(
            trainer_client,
            "trainer@example.com",
            delivered["temporary_password"],
        )
        assert first_login.status_code == 200
        assert first_login.json()["data"]["password_change_required"] is True
        assert trainer_client.cookies.get("temp_token")

        without_csrf = await trainer_client.post(
            "/api/auth/first-time-password-change",
            json={"new_password": "TrainerSecure123!", "confirm_password": "TrainerSecure123!"},
        )
        assert without_csrf.status_code == 403

        activated = await trainer_client.post(
            "/api/auth/first-time-password-change",
            headers=csrf_headers(trainer_client),
            json={"new_password": "TrainerSecure123!", "confirm_password": "TrainerSecure123!"},
        )
        assert activated.status_code == 200
        assert trainer_client.cookies.get("temp_token") is None

        authenticated = await trainer_client.get("/api/auth/check-auth")
        assert authenticated.status_code == 200
        assert authenticated.json()["data"]["user"]["is_password_changed"] is True

        old_refresh = trainer_client.cookies["refresh_token"]
        refreshed = await trainer_client.post(
            "/api/auth/refresh",
            headers=csrf_headers(trainer_client),
        )
        assert refreshed.status_code == 200
        assert trainer_client.cookies["refresh_token"] != old_refresh

        async with AsyncClient(transport=transport, base_url="http://testserver") as replay_client:
            replay_client.cookies.set("refresh_token", old_refresh)
            replay_client.cookies.set(settings.CSRF_COOKIE_NAME, "replay-csrf-token")
            replay = await replay_client.post(
                "/api/auth/refresh",
                headers={settings.CSRF_HEADER_NAME: "replay-csrf-token"},
            )
        assert replay.status_code == 401
        assert "reuse" in replay.json()["message"].lower()

        revoked = await trainer_client.get("/api/auth/check-auth")
        assert revoked.status_code == 401

    deactivated = await client.patch(
        f"/api/auth/users/{invited_user['id']}/status",
        headers=csrf_headers(client),
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["user"]["is_active"] is False


async def test_user_is_preserved_when_invitation_delivery_fails(
    client: AsyncClient,
    monkeypatch,
) -> None:
    async def reject_invitation(**_: str) -> bool:
        return False

    monkeypatch.setattr(email_service, "send_temporary_password", reject_invitation)
    admin_login = await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    assert admin_login.status_code == 200

    invitation = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "pending-trainer@example.com",
            "first_name": "Pending",
            "last_name": "Trainer",
            "role": "trainer",
            "phone_number": "+254700000020",
            "employee_id": "TR-020",
        },
    )

    assert invitation.status_code == 201
    assert invitation.json()["data"]["invitation_sent"] is False
    assert "not delivered" in invitation.json()["message"]

    listing = await client.get("/api/auth/users", params={"role": "trainer"})
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    assert listing.json()["data"]["users"][0]["email"] == "pending-trainer@example.com"
    assert listing.json()["data"]["users"][0]["is_password_changed"] is False


async def test_password_reset_uses_one_time_hashed_code(client: AsyncClient, monkeypatch) -> None:
    invitation: dict[str, str] = {}
    reset_delivery: dict[str, str] = {}

    async def capture_invitation(**kwargs: str) -> bool:
        invitation.update(kwargs)
        return True

    async def capture_reset(**kwargs: str) -> bool:
        reset_delivery.update(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_temporary_password", capture_invitation)
    monkeypatch.setattr(email_service, "send_password_reset_code", capture_reset)

    await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    created = await client.post(
        "/api/auth/users",
        headers=csrf_headers(client),
        json={
            "email": "agent@example.com",
            "first_name": "Field",
            "last_name": "Agent",
            "role": "agent",
            "phone_number": "+254700000030",
            "agent_code": "AGT-030",
        },
    )
    assert created.status_code == 201

    forgot = await client.post("/api/auth/forgot-password", json={"email": "agent@example.com"})
    assert forgot.status_code == 200
    assert reset_delivery["code"]

    reset = await client.post(
        "/api/auth/reset-password",
        json={
            "email": "agent@example.com",
            "otp_code": reset_delivery["code"],
            "new_password": "ResetSecure123!",
            "confirm_password": "ResetSecure123!",
        },
    )
    assert reset.status_code == 200

    reused = await client.post(
        "/api/auth/reset-password",
        json={
            "email": "agent@example.com",
            "otp_code": reset_delivery["code"],
            "new_password": "AnotherSecure123!",
            "confirm_password": "AnotherSecure123!",
        },
    )
    assert reused.status_code == 400

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as agent_client:
        response = await login(agent_client, "agent@example.com", "ResetSecure123!")
        assert response.status_code == 200
        assert response.json()["data"]["password_change_required"] is False
