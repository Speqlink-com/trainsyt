"""Persistence helpers for revocable, rotating authentication sessions."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.core.security import utcnow
from app.models.sessions import Session


class SessionRepository:
    async def create_session(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        user_id: UUID,
        access_token_hash: str,
        refresh_token_hash: str,
        expires_in_minutes: int,
        refresh_expires_in_days: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_type: str | None = None,
    ) -> Session:
        now = utcnow()
        session = Session(
            id=session_id,
            user_id=user_id,
            access_token_hash=access_token_hash,
            refresh_token_hash=refresh_token_hash,
            expires_at=now + timedelta(minutes=expires_in_minutes),
            refresh_expires_at=now + timedelta(days=refresh_expires_in_days),
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            last_used_at=now,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session_by_id(
        self,
        db: AsyncSession,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> Session | None:
        statement = select(Session).where(Session.id == session_id)
        if for_update:
            statement = statement.with_for_update()
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_session_by_access_token_hash(
        self,
        db: AsyncSession,
        access_token_hash: str,
    ) -> Session | None:
        result = await db.execute(
            select(Session).where(
                Session.access_token_hash == access_token_hash,
                Session.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def rotate_session_tokens(
        self,
        db: AsyncSession,
        *,
        session: Session,
        access_token_hash: str,
        refresh_token_hash: str,
        expires_in_minutes: int,
        refresh_expires_in_days: int,
    ) -> Session:
        now = utcnow()
        session.access_token_hash = access_token_hash
        session.refresh_token_hash = refresh_token_hash
        session.expires_at = now + timedelta(minutes=expires_in_minutes)
        session.refresh_expires_at = now + timedelta(days=refresh_expires_in_days)
        session.last_used_at = now
        session.updated_at = now
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def revoke_session(self, db: AsyncSession, session: Session) -> None:
        if session.is_active:
            session.revoke()
            db.add(session)
            await db.commit()

    async def revoke_all_user_sessions(self, db: AsyncSession, user_id: UUID) -> int:
        result = await db.execute(
            select(Session).where(Session.user_id == user_id, Session.is_active.is_(True))
        )
        sessions = list(result.scalars().all())
        for session in sessions:
            session.revoke()
            db.add(session)
        await db.commit()
        return len(sessions)

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        result = await db.execute(delete(Session).where(Session.refresh_expires_at < utcnow()))
        await db.commit()
        return result.rowcount or 0


session_repository = SessionRepository()
