"""Async database engine, request sessions, and readiness checks."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.core import settings

logger = logging.getLogger(__name__)


def async_database_url() -> str:
    """Normalize common database URLs to an async SQLAlchemy driver."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername == "sqlite":
        url = url.set(drivername="sqlite+aiosqlite")
    return url.render_as_string(hide_password=False)


engine_options: dict[str, object] = {
    "echo": settings.DATABASE_ECHO or settings.DEBUG,
    "pool_pre_ping": True,
}
if async_database_url().startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(async_database_url(), **engine_options)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def database_ready() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", exc)
        return False


async def dispose_database() -> None:
    await engine.dispose()
