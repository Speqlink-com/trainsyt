"""Idempotently create the environment-configured initial administrator."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.core import settings
from app.core.database import async_session, dispose_database
from app.core.security import hash_password, utcnow, validate_password_strength
from app.models.enums import UserRole
from app.models.users import User
from app.repositories.user_repository import user_repository

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def seed_admin(db: AsyncSession) -> bool:
    """Create the configured super administrator once.

    Returns True when a row is created and False when the configured account
    already exists. Existing credentials are never silently overwritten.
    """

    if not settings.SEED_ADMIN_EMAIL or not settings.SEED_ADMIN_PASSWORD:
        raise RuntimeError("SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD must be configured")

    email = settings.SEED_ADMIN_EMAIL.strip().lower()
    password = settings.SEED_ADMIN_PASSWORD.get_secret_value()
    valid, message = validate_password_strength(password)
    if not valid:
        raise RuntimeError(f"SEED_ADMIN_PASSWORD is invalid: {message}")

    existing = await user_repository.get_user_by_email(db, email)
    if existing:
        if existing.role != UserRole.SUPER_ADMIN:
            raise RuntimeError(f"The seed email {email} belongs to a non-super-admin account")
        logger.info("Seed administrator already exists: %s", email)
        return False

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name=settings.SEED_ADMIN_FIRST_NAME.strip(),
        last_name=settings.SEED_ADMIN_LAST_NAME.strip(),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_password_changed=True,
        is_email_verified=True,
        verified_at=utcnow(),
        last_password_change_at=utcnow(),
    )
    db.add(user)
    await db.commit()
    logger.info("Created seed administrator: %s", email)
    return True


async def main() -> None:
    try:
        async with async_session() as db:
            await seed_admin(db)
    finally:
        await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())
