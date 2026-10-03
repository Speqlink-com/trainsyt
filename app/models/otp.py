"""OTP model for one-time password verification."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, naive_utcnow
from app.models.enums import OTPPurpose


class OTP(TimestampMixin, SQLModel, table=True):
    """One-time password model for verification."""

    __tablename__ = "otps"

    # ========================================================================
    # PRIMARY IDENTIFICATION
    # ========================================================================
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # ========================================================================
    # OTP DATA
    # ========================================================================
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)

    # OTP details
    hashed_code: str = Field(max_length=64, nullable=False, index=True)
    purpose: OTPPurpose = Field(nullable=False, index=True)

    # Expiry and usage
    expires_at: datetime = Field(nullable=False, index=True)
    used_at: datetime | None = Field(default=None)
    attempts: int = Field(default=0)

    # Status
    is_active: bool = Field(default=True, index=True)

    @property
    def is_expired(self) -> bool:
        """Check if OTP is expired."""
        return naive_utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if OTP has been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if OTP is valid (active, not expired, not used)."""
        return self.is_active and not self.is_expired and not self.is_used

    def mark_as_used(self) -> None:
        """Mark OTP as used."""
        self.used_at = naive_utcnow()
        self.is_active = False

    def increment_attempt(self) -> None:
        """Increment attempt counter."""
        self.attempts += 1

    @classmethod
    def create_expiry(cls, minutes: int = 5) -> datetime:
        """Create expiry datetime."""
        return naive_utcnow() + timedelta(minutes=minutes)

    def __repr__(self) -> str:
        return f"<OTP(user_id={self.user_id}, purpose={self.purpose}, active={self.is_active})>"
