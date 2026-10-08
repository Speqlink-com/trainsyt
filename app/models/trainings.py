"""Training programmes, QR registrations, and attendance records."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin
from app.models.enums import AttendanceStatus, ParticipantRole, TrainingStatus


class Training(TimestampMixin, SQLModel, table=True):
    """A trainer-owned programme that exposes a shareable public QR code."""

    __tablename__ = "trainings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    public_code: str = Field(max_length=64, nullable=False, unique=True, index=True)
    title: str = Field(max_length=200, nullable=False, index=True)
    description: str = Field(default="", max_length=2000)
    trainer_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    created_by_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    scheduled_at: datetime = Field(nullable=False, index=True)
    duration_hours: float = Field(default=1.0, gt=0)
    location: str = Field(max_length=300, nullable=False)
    audience_roles: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    capacity: int = Field(default=40, gt=0)
    status: TrainingStatus = Field(default=TrainingStatus.SCHEDULED, nullable=False, index=True)
    attendance_open: bool = Field(default=True, nullable=False, index=True)
    trainer_reminder_sent_at: datetime | None = Field(default=None, nullable=True)


class TrainingRegistration(TimestampMixin, SQLModel, table=True):
    """A participant who joined a programme using its public link."""

    __tablename__ = "training_registrations"
    __table_args__ = (
        UniqueConstraint(
            "training_id",
            "participant_code",
            name="uq_training_registration_identity",
        ),
        UniqueConstraint("training_id", "phone", name="uq_training_registration_phone"),
        UniqueConstraint("training_id", "email", name="uq_training_registration_email"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    training_id: UUID = Field(foreign_key="trainings.id", nullable=False, index=True)
    participant_name: str = Field(max_length=200, nullable=False, index=True)
    participant_code: str = Field(max_length=100, nullable=False, index=True)
    role: ParticipantRole = Field(nullable=False, index=True)
    email: str | None = Field(default=None, max_length=255, index=True)
    phone: str | None = Field(default=None, max_length=30)
    joined_at: datetime = Field(nullable=False, index=True)
    source: str = Field(default="qr_link", max_length=30)
    reminder_sent_at: datetime | None = Field(default=None, nullable=True)


class TrainingAttendance(TimestampMixin, SQLModel, table=True):
    """An idempotent attendance confirmation for one registration."""

    __tablename__ = "training_attendance"
    __table_args__ = (UniqueConstraint("registration_id", name="uq_training_attendance_registration"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    training_id: UUID = Field(foreign_key="trainings.id", nullable=False, index=True)
    registration_id: UUID = Field(
        foreign_key="training_registrations.id",
        nullable=False,
        index=True,
    )
    status: AttendanceStatus = Field(default=AttendanceStatus.PRESENT, nullable=False, index=True)
    checked_in_at: datetime = Field(nullable=False, index=True)
    source: str = Field(default="qr", max_length=30)
    ip_address: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=500)
