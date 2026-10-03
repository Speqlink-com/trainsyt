"""User model for authentication and authorization."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.base import SoftDeleteMixin, TimestampMixin
from app.models.enums import UserRole


class User(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    """User model - handles authentication and authorization."""

    __tablename__ = "users"

    # ========================================================================
    # PRIMARY IDENTIFICATION
    # ========================================================================
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # ========================================================================
    # AUTHENTICATION FIELDS
    # ========================================================================
    email: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
        index=True,
    )
    hashed_password: str = Field(max_length=255)

    # ========================================================================
    # PROFILE INFORMATION
    # ========================================================================
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)
    profile_pic_url: str | None = Field(default=None, max_length=500)

    # ========================================================================
    # ROLE & PERMISSIONS
    # ========================================================================
    role: UserRole = Field(index=True)

    # ========================================================================
    # TRAINING SPECIFIC FIELDS
    # ========================================================================
    employee_id: str | None = Field(default=None, max_length=50, index=True)
    branch_id: str | None = Field(default=None, max_length=50, index=True)
    department: str | None = Field(default=None, max_length=100)

    # For Sales Managers and HOAs
    territory: str | None = Field(default=None, max_length=100)

    # For Trainers
    specializations: str | None = Field(default=None, max_length=500)  # JSON string of specializations

    # For Agents
    agent_code: str | None = Field(default=None, max_length=20, unique=True, index=True)
    sm_id: UUID | None = Field(default=None, foreign_key="users.id")  # Sales Manager
    hoa_id: UUID | None = Field(default=None, foreign_key="users.id")  # Head of Agency
    date_appointed: datetime | None = Field(default=None)

    # ========================================================================
    # STATUS & SECURITY
    # ========================================================================
    is_active: bool = Field(default=True, index=True)
    is_password_changed: bool = Field(default=False)
    is_email_verified: bool = Field(default=False)
    token_version: int = Field(default=0, nullable=False)

    # ========================================================================
    # AUDIT FIELDS
    # ========================================================================
    created_by_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )

    last_login_at: datetime | None = Field(default=None)
    last_password_change_at: datetime | None = Field(default=None)

    # Security tracking
    failed_login_attempts: int = Field(default=0)
    locked_until: datetime | None = Field(default=None)

    # ========================================================================
    # VERIFICATION
    # ========================================================================
    verified_at: datetime | None = Field(default=None)
    verified_by: UUID | None = Field(default=None)

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:
        return f"<User(email={self.email}, role={self.role})>"
