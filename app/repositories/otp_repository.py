"""OTP repository for managing one-time passwords."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import and_, delete, select

from app.core.core import settings
from app.models.base import naive_utcnow
from app.models.enums import OTPPurpose
from app.models.otp import OTP

logger = logging.getLogger(__name__)


class OTPRepository:
    """Repository for OTP management operations."""

    async def create_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        hashed_code: str,
        purpose: OTPPurpose,
        expires_in_minutes: int = 5,
    ) -> OTP:
        """Create a new OTP."""

        # Deactivate existing OTPs for the same user and purpose
        await self.deactivate_user_otps(db, user_id, purpose)

        otp = OTP(
            user_id=user_id,
            hashed_code=hashed_code,
            purpose=purpose,
            expires_at=naive_utcnow() + timedelta(minutes=expires_in_minutes),
        )

        db.add(otp)
        await db.commit()
        await db.refresh(otp)

        logger.info(f"Created OTP for user {user_id} with purpose {purpose}")
        return otp

    async def get_otp_by_hash(
        self,
        db: AsyncSession,
        hashed_code: str,
        user_id: UUID,
        purpose: OTPPurpose,
    ) -> OTP | None:
        """Get OTP by hashed code, user, and purpose."""

        statement = select(OTP).where(
            and_(
                OTP.hashed_code == hashed_code,
                OTP.user_id == user_id,
                OTP.purpose == purpose,
                OTP.is_active.is_(True),
            )
        )
        result = await db.execute(statement)
        return result.scalars().first()

    async def get_valid_otp(
        self,
        db: AsyncSession,
        user_id: UUID,
        purpose: OTPPurpose,
    ) -> OTP | None:
        """Get valid (active, not expired, not used) OTP for user and purpose."""

        now = naive_utcnow()

        statement = (
            select(OTP)
            .where(
                and_(
                    OTP.user_id == user_id,
                    OTP.purpose == purpose,
                    OTP.is_active.is_(True),
                    OTP.expires_at > now,
                    OTP.used_at.is_(None),
                )
            )
            .order_by(OTP.created_at.desc())
        )

        result = await db.execute(statement)
        return result.scalars().first()

    async def mark_otp_as_used(
        self,
        db: AsyncSession,
        otp: OTP,
    ) -> None:
        """Mark OTP as used."""

        otp.mark_as_used()
        await db.commit()

        logger.info(f"Marked OTP as used for user {otp.user_id}")

    async def increment_otp_attempt(
        self,
        db: AsyncSession,
        otp: OTP,
    ) -> None:
        """Increment OTP attempt counter."""

        otp.increment_attempt()

        # Deactivate OTP after the configured limit. The service may also
        # reject it earlier when the configured threshold is reached.
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp.is_active = False
            logger.warning(
                "OTP deactivated for user %s after %s failed attempts",
                otp.user_id,
                settings.OTP_MAX_ATTEMPTS,
            )

        await db.commit()

    async def deactivate_user_otps(
        self,
        db: AsyncSession,
        user_id: UUID,
        purpose: OTPPurpose,
    ) -> int:
        """Deactivate all active OTPs for a user and purpose."""

        statement = select(OTP).where(
            and_(
                OTP.user_id == user_id,
                OTP.purpose == purpose,
                OTP.is_active.is_(True),
            )
        )
        result = await db.execute(statement)
        otps = result.scalars().all()

        count = 0
        for otp in otps:
            otp.is_active = False
            count += 1

        await db.commit()

        if count > 0:
            logger.info(f"Deactivated {count} OTPs for user {user_id} with purpose {purpose}")

        return count

    async def cleanup_expired_otps(
        self,
        db: AsyncSession,
    ) -> int:
        """Clean up expired OTPs."""

        # Delete OTPs that expired more than 1 day ago
        cutoff_time = naive_utcnow() - timedelta(days=1)

        statement = delete(OTP).where(OTP.expires_at < cutoff_time)

        result = await db.execute(statement)
        await db.commit()

        count = result.rowcount or 0
        logger.info(f"Cleaned up {count} expired OTPs")
        return count

    async def get_recent_otp_count(
        self,
        db: AsyncSession,
        user_id: UUID,
        purpose: OTPPurpose,
        minutes: int = 10,
    ) -> int:
        """Get count of OTPs created for user in recent minutes."""

        cutoff_time = naive_utcnow() - timedelta(minutes=minutes)

        statement = select(OTP).where(
            and_(
                OTP.user_id == user_id,
                OTP.purpose == purpose,
                OTP.created_at > cutoff_time,
            )
        )
        result = await db.execute(statement)
        otps = result.scalars().all()

        return len(otps)


# Create repository instance
otp_repository = OTPRepository()
