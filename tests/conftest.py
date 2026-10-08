"""Isolated application and database fixtures."""

import os
from collections.abc import AsyncGenerator
from tempfile import gettempdir

os.environ.update(
    {
        "DATABASE_URL": (
            f"sqlite+aiosqlite:///{gettempdir()}/trainsyt-pytest-{os.getpid()}.sqlite"
        ),
        "ENVIRONMENT": "test",
        "JWT_SECRET": "test-jwt-signing-secret-with-at-least-thirty-two-characters",
        "INITIAL_ADMIN_SECRET_KEY": "test-bootstrap-secret-with-at-least-thirty-two-characters",
        "SEED_ADMIN_EMAIL": "admin@example.com",
        "SEED_ADMIN_PASSWORD": "AdminTest123!",
        "SEED_ADMIN_FIRST_NAME": "Test",
        "SEED_ADMIN_LAST_NAME": "Administrator",
        "ZOHO_EMAIL": "mailer@example.com",
        "ZOHO_APP_PASSWORD": "test-smtp-password",
        "EMAIL_FROM": "mailer@example.com",
        "SMTP_STARTTLS": "true",
        "EMAIL_DELIVERY_MODE": "console",
        "TRAINING_REMINDERS_ENABLED": "false",
        "COOKIE_SECURE": "false",
        "COOKIE_DOMAIN": ".testserver.local",
        "COOKIE_SAMESITE": "lax",
        "TRUSTED_HOSTS": "testserver.local,localhost,127.0.0.1",
        "CORS_ORIGINS": "http://localhost:3000",
        "FRONTEND_URL": "http://localhost:3000",
    }
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel

from app.core.database import async_session, engine
from app.scripts.seed_admin import seed_admin
from main import app


@pytest_asyncio.fixture(autouse=True)
async def isolated_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)
        await connection.run_sync(SQLModel.metadata.create_all)
    async with async_session() as db:
        await seed_admin(db)
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver.local") as test_client:
        yield test_client
