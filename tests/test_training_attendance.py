"""Integration coverage for QR registration, attendance, and Excel export."""

from datetime import timedelta
from io import BytesIO
from uuid import UUID

from httpx import AsyncClient
from openpyxl import load_workbook

from app.core.core import settings
from app.core.database import async_session
from app.core.security import hash_password, utcnow
from app.models.enums import UserRole
from app.models.trainings import Training
from app.models.users import User
from app.services.email_service import email_service
from app.services.training_reminder_service import training_reminder_service


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]}


async def login(client: AsyncClient, email: str, password: str):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def create_trainer(email: str = "trainer@example.com") -> User:
    async with async_session() as db:
        trainer = User(
            email=email,
            hashed_password=hash_password("TrainerSecure123!"),
            first_name="Training",
            last_name="Lead",
            role=UserRole.TRAINER,
            employee_id=f"TR-{email.split('@')[0].upper()}",
            is_active=True,
            is_password_changed=True,
            is_email_verified=True,
        )
        db.add(trainer)
        await db.commit()
        await db.refresh(trainer)
        return trainer


async def create_programme(
    client: AsyncClient,
    trainer: User,
    *,
    capacity: int = 20,
    starts_in_minutes: int = 120,
) -> dict:
    response = await client.post(
        "/api/trainings",
        headers=csrf_headers(client),
        json={
            "title": "AML and compliance essentials",
            "description": "Annual customer due diligence and escalation training.",
            "trainer_id": str(trainer.id),
            "scheduled_at": (utcnow() + timedelta(minutes=starts_in_minutes)).isoformat() + "Z",
            "duration_hours": 3,
            "location": "Nairobi Learning Centre - Room 4",
            "audience_roles": ["agent", "sales_manager", "hoa", "trainer"],
            "capacity": capacity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["training"]


async def start_programme(training_id: str) -> None:
    async with async_session() as db:
        training = await db.get(Training, UUID(training_id))
        assert training
        training.scheduled_at = utcnow() - timedelta(seconds=1)
        db.add(training)
        await db.commit()


async def test_qr_registration_attendance_and_excel_export(client: AsyncClient) -> None:
    trainer = await create_trainer()
    admin_login = await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    assert admin_login.status_code == 200
    training = await create_programme(client, trainer)
    public_code = training["public_code"]

    public_view = await client.get(f"/api/public/trainings/{public_code}")
    assert public_view.status_code == 200
    assert public_view.json()["data"]["training"]["title"] == training["title"]
    assert public_view.json()["data"]["training"]["scheduled_at"].endswith("Z")

    wrong_role = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json={
            "participant_name": "External Guest",
            "participant_code": "GUEST-01",
            "role": "guest",
            "email": "guest@example.com",
            "phone": "+254700000099",
        },
    )
    assert wrong_role.status_code == 422

    registration_payload = {
        "participant_name": "Emma Johnson",
        "participant_code": "agt-001234",
        "role": "agent",
        "email": "emma@example.com",
        "phone": "+254700000001",
    }
    joined = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json=registration_payload,
    )
    assert joined.status_code == 201, joined.text
    registration = joined.json()["data"]["registration"]
    assert registration["participant_code"] == "AGT-001234"
    assert registration["phone"] == "+254700000001"
    assert registration["attendance_marked"] is False
    assert registration["joined_at"].endswith("Z")

    duplicate = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json=registration_payload,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["data"]["registration"]["id"] == registration["id"]

    reused_code = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json={**registration_payload, "participant_name": "Different Person"},
    )
    assert reused_code.status_code == 409

    reused_phone = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json={
            **registration_payload,
            "participant_code": "AGT-001235",
            "email": "different@example.com",
        },
    )
    assert reused_phone.status_code == 409

    invalid_phone = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json={
            **registration_payload,
            "participant_code": "AGT-001236",
            "email": "valid@example.com",
            "phone": "not-a-phone",
        },
    )
    assert invalid_phone.status_code == 422

    too_early = await client.post(
        f"/api/public/trainings/{public_code}/attendance",
        json={"registration_token": registration["registration_token"]},
    )
    assert too_early.status_code == 409
    assert "scheduled meeting time" in too_early.json()["detail"].lower()

    await start_programme(training["id"])

    rejected = await client.post(
        f"/api/public/trainings/{public_code}/attendance",
        json={"registration_token": registration["registration_token"] + "tampered"},
    )
    assert rejected.status_code == 401

    marked = await client.post(
        f"/api/public/trainings/{public_code}/attendance",
        json={"registration_token": registration["registration_token"]},
    )
    assert marked.status_code == 200, marked.text
    attendance = marked.json()["data"]["attendance"]
    assert attendance["status"] == "present"

    repeated = await client.post(
        f"/api/public/trainings/{public_code}/attendance",
        json={"registration_token": registration["registration_token"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["attendance"]["id"] == attendance["id"]

    register = await client.get("/api/trainings/attendance", params={"training_id": training["id"]})
    assert register.status_code == 200
    rows = register.json()["data"]["rows"]
    assert len(rows) == 1
    assert rows[0]["attendance_status"] == "present"

    export = await client.get(
        "/api/trainings/attendance/export.xlsx",
        params={"training_id": training["id"]},
    )
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(export.content), data_only=False)
    worksheet = workbook["Attendance"]
    assert worksheet["A1"].value == "Jubilee training attendance register"
    assert worksheet["A7"].value == training["title"]
    assert worksheet["E7"].value == "Emma Johnson"
    assert worksheet["K7"].value == "Present"
    assert worksheet.freeze_panes == "A7"
    assert worksheet.auto_filter.ref == "A6:L7"
    workbook.close()


async def test_one_hour_reminders_are_sent_once(client: AsyncClient, monkeypatch) -> None:
    deliveries: list[dict] = []

    async def capture_reminder(**kwargs) -> bool:
        deliveries.append(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_training_reminder", capture_reminder)
    trainer = await create_trainer("reminder-trainer@example.com")
    await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    training = await create_programme(client, trainer, starts_in_minutes=30)
    joined = await client.post(
        f"/api/public/trainings/{training['public_code']}/registrations",
        json={
            "participant_name": "Reminder Recipient",
            "participant_code": "AGT-REM-01",
            "role": "agent",
            "email": "recipient@example.com",
            "phone": "+254700000041",
        },
    )
    assert joined.status_code == 201

    async with async_session() as db:
        first = await training_reminder_service.dispatch_due_reminders(db)
    assert first.trainer_emails == 1
    assert first.participant_emails == 1
    assert {item["email"] for item in deliveries} == {
        "reminder-trainer@example.com",
        "recipient@example.com",
    }

    async with async_session() as db:
        repeated = await training_reminder_service.dispatch_due_reminders(db)
    assert repeated.trainer_emails == 0
    assert repeated.participant_emails == 0
    assert len(deliveries) == 2


async def test_admin_can_update_and_delete_programme(client: AsyncClient) -> None:
    trainer = await create_trainer("crud-trainer@example.com")
    await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    training = await create_programme(client, trainer)
    assert training["scheduled_at"].endswith("Z")
    assert training["created_at"].endswith("Z")
    assert training["updated_at"].endswith("Z")
    registration = await client.post(
        f"/api/public/trainings/{training['public_code']}/registrations",
        json={
            "participant_name": "Registered Agent",
            "participant_code": "AGT-CRUD-01",
            "role": "agent",
            "email": "crud-agent@example.com",
            "phone": "+254700000051",
        },
    )
    assert registration.status_code == 201

    invalid_audience = await client.patch(
        f"/api/trainings/{training['id']}",
        headers=csrf_headers(client),
        json={"audience_roles": ["trainer"]},
    )
    assert invalid_audience.status_code == 409

    new_time = utcnow() + timedelta(days=2)
    updated = await client.patch(
        f"/api/trainings/{training['id']}",
        headers=csrf_headers(client),
        json={
            "title": "Updated compliance programme",
            "description": "Updated by the administrator.",
            "trainer_id": str(trainer.id),
            "scheduled_at": new_time.isoformat() + "Z",
            "duration_hours": 2.5,
            "location": "https://meet.example.com/updated",
            "audience_roles": ["agent", "trainer"],
            "capacity": 25,
            "status": "scheduled",
            "attendance_open": True,
            "expected_updated_at": training["updated_at"],
        },
    )
    assert updated.status_code == 200, updated.text
    updated_training = updated.json()["data"]["training"]
    assert updated_training["title"] == "Updated compliance programme"
    assert updated_training["capacity"] == 25
    assert updated_training["scheduled_at"].endswith("Z")
    assert updated_training["updated_at"].endswith("Z")

    persisted = await client.get(f"/api/trainings/{training['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["data"]["training"]["title"] == "Updated compliance programme"

    stale_update = await client.patch(
        f"/api/trainings/{training['id']}",
        headers=csrf_headers(client),
        json={
            "title": "Stale browser update",
            "expected_updated_at": training["updated_at"],
        },
    )
    assert stale_update.status_code == 409
    assert "changed by another administrator" in stale_update.json()["detail"]

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, trainer.email, "TrainerSecure123!")
    forbidden = await client.delete(
        f"/api/trainings/{training['id']}",
        headers=csrf_headers(client),
    )
    assert forbidden.status_code == 403

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    deleted = await client.delete(
        f"/api/trainings/{training['id']}",
        headers=csrf_headers(client),
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_registrations"] == 1
    assert deleted.json()["data"]["deleted_attendance_records"] == 0
    missing = await client.get(f"/api/trainings/{training['id']}")
    assert missing.status_code == 404
    public_missing = await client.get(f"/api/public/trainings/{training['public_code']}")
    assert public_missing.status_code == 404


async def test_trainer_only_sees_and_exports_assigned_programmes(client: AsyncClient) -> None:
    assigned_trainer = await create_trainer("assigned@example.com")
    other_trainer = await create_trainer("other@example.com")
    await login(
        client,
        settings.SEED_ADMIN_EMAIL or "",
        settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
    )
    training = await create_programme(client, assigned_trainer)

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    trainer_login = await login(client, "assigned@example.com", "TrainerSecure123!")
    assert trainer_login.status_code == 200
    assigned_list = await client.get("/api/trainings")
    assert [item["id"] for item in assigned_list.json()["data"]["trainings"]] == [training["id"]]
    assigned_export = await client.get("/api/trainings/attendance/export.xlsx")
    assert assigned_export.status_code == 200

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    other_login = await login(client, other_trainer.email, "TrainerSecure123!")
    assert other_login.status_code == 200
    other_list = await client.get("/api/trainings")
    assert other_list.json()["data"]["trainings"] == []
    forbidden = await client.get(f"/api/trainings/{training['id']}")
    assert forbidden.status_code == 403
