"""Session model for managing user authentication sessions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, naive_utcnow


class Session(TimestampMixin, SQLModel, table=True):
    """User session model for JWT token management."""

    __tablename__ = "sessions"

    # ========================================================================
    # PRIMARY IDENTIFICATION
    # ========================================================================
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # ========================================================================
    # SESSION DATA
    # ========================================================================
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)

    # Token hashes for security (never store actual tokens)
    access_token_hash: str = Field(max_length=64, nullable=False, index=True)
    refresh_token_hash: str = Field(max_length=64, nullable=False, index=True)

    # Session metadata
    ip_address: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=500)
    device_type: str | None = Field(default=None, max_length=20)

    # Expiry tracking
    expires_at: datetime = Field(nullable=False, index=True)
    refresh_expires_at: datetime = Field(nullable=False, index=True)

    # Session status
    is_active: bool = Field(default=True, index=True)
    revoked_at: datetime | None = Field(default=None)
    last_used_at: datetime | None = Field(default=None)

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return naive_utcnow() > self.expires_at

    @property
    def is_refresh_expired(self) -> bool:
        """Check if refresh token is expired."""
        return naive_utcnow() > self.refresh_expires_at

    def revoke(self) -> None:
        """Revoke the session."""
        self.is_active = False
        self.revoked_at = naive_utcnow()

    def __repr__(self) -> str:
        return f"<Session(user_id={self.user_id}, active={self.is_active})>"
