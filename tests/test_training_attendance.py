"""Integration coverage for QR registration, attendance, and Excel export."""

from io import BytesIO

from httpx import AsyncClient
from openpyxl import load_workbook

from app.core.core import settings
from app.core.database import async_session
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.users import User


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
            employee_id="TR-001",
            is_active=True,
            is_password_changed=True,
            is_email_verified=True,
        )
        db.add(trainer)
        await db.commit()
        await db.refresh(trainer)
        return trainer


async def create_programme(client: AsyncClient, trainer: User, *, capacity: int = 20) -> dict:
    response = await client.post(
        "/api/trainings",
        headers=csrf_headers(client),
        json={
            "title": "AML and compliance essentials",
            "description": "Annual customer due diligence and escalation training.",
            "trainer_id": str(trainer.id),
            "scheduled_at": "2026-10-02T09:30:00",
            "duration_hours": 3,
            "location": "Nairobi Learning Centre - Room 4",
            "audience_roles": ["agent", "sales_manager", "hoa", "trainer"],
            "capacity": capacity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["training"]


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

    wrong_role = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json={
            "participant_name": "External Guest",
            "participant_code": "GUEST-01",
            "role": "guest",
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
    assert registration["attendance_marked"] is False

    duplicate = await client.post(
        f"/api/public/trainings/{public_code}/registrations",
        json=registration_payload,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["data"]["registration"]["id"] == registration["id"]

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
