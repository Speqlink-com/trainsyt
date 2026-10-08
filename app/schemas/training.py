"""Schemas for training programmes and QR attendance."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator, model_validator

from app.core.identity import normalize_person_name, normalize_personnel_code, normalize_phone_number
from app.models.enums import AttendanceStatus, ParticipantRole, TrainingStatus


def utc_iso(value: datetime | None) -> str | None:
    """Serialize the database's naive-UTC timestamps as unambiguous UTC values."""

    if value is None:
        return None
    aware_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware_value.isoformat().replace("+00:00", "Z")


class TrainingCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    trainer_id: UUID | None = None
    scheduled_at: datetime
    duration_hours: float = Field(gt=0, le=24)
    location: str = Field(min_length=2, max_length=300)
    audience_roles: list[ParticipantRole] = Field(min_length=1)
    capacity: int = Field(ge=1, le=10000)

    @field_validator("title", "description", "location")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("scheduled_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Programme date and time must include a timezone")
        return value

    @field_validator("audience_roles")
    @classmethod
    def unique_roles(cls, value: list[ParticipantRole]) -> list[ParticipantRole]:
        return list(dict.fromkeys(value))


class TrainingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    trainer_id: UUID | None = None
    scheduled_at: datetime | None = None
    duration_hours: float | None = Field(default=None, gt=0, le=24)
    location: str | None = Field(default=None, min_length=2, max_length=300)
    audience_roles: list[ParticipantRole] | None = Field(default=None, min_length=1)
    capacity: int | None = Field(default=None, ge=1, le=10000)
    status: TrainingStatus | None = None
    attendance_open: bool | None = None
    expected_updated_at: datetime | None = None

    @field_validator("title", "description", "location")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("scheduled_at", "expected_updated_at")
    @classmethod
    def update_timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Programme date and time must include a timezone")
        return value

    @field_validator("audience_roles")
    @classmethod
    def unique_optional_roles(
        cls,
        value: list[ParticipantRole] | None,
    ) -> list[ParticipantRole] | None:
        return list(dict.fromkeys(value)) if value is not None else None

    @model_validator(mode="after")
    def has_update(self) -> "TrainingUpdateRequest":
        if not (self.model_fields_set - {"expected_updated_at"}):
            raise ValueError("At least one programme field is required")
        return self


class TrainingStatusUpdateRequest(BaseModel):
    status: TrainingStatus | None = None
    attendance_open: bool | None = None

    @model_validator(mode="after")
    def has_update(self) -> "TrainingStatusUpdateRequest":
        if self.status is None and self.attendance_open is None:
            raise ValueError("At least one training status field is required")
        return self


class PublicRegistrationRequest(BaseModel):
    participant_name: str = Field(min_length=2, max_length=200)
    participant_code: str = Field(min_length=2, max_length=50)
    role: ParticipantRole
    email: EmailStr
    phone: str = Field(max_length=30)

    @field_validator("participant_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return normalize_person_name(value)

    @field_validator("participant_code")
    @classmethod
    def valid_code(cls, value: str) -> str:
        return normalize_personnel_code(value)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        return normalize_phone_number(value)


class AttendanceMarkRequest(BaseModel):
    registration_token: str = Field(min_length=32)


class TrainingResponse(BaseModel):
    id: UUID
    public_code: str
    title: str
    description: str
    trainer_id: UUID
    trainer_name: str
    scheduled_at: datetime
    duration_hours: float
    location: str
    audience_roles: list[ParticipantRole]
    capacity: int
    status: TrainingStatus
    attendance_open: bool
    registration_count: int
    attendance_count: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("scheduled_at", "created_at", "updated_at", when_used="json")
    def serialize_utc_datetime(self, value: datetime) -> str | None:
        return utc_iso(value)


class PublicTrainingResponse(BaseModel):
    public_code: str
    title: str
    description: str
    trainer_name: str
    scheduled_at: datetime
    duration_hours: float
    location: str
    audience_roles: list[ParticipantRole]
    capacity: int
    status: TrainingStatus
    attendance_open: bool
    registration_count: int

    @field_serializer("scheduled_at", when_used="json")
    def serialize_scheduled_at(self, value: datetime) -> str | None:
        return utc_iso(value)


class RegistrationResponse(BaseModel):
    id: UUID
    training_id: UUID
    participant_name: str
    participant_code: str
    role: ParticipantRole
    email: str | None
    phone: str | None
    joined_at: datetime
    attendance_marked: bool
    checked_in_at: datetime | None
    registration_token: str

    @field_serializer("joined_at", "checked_in_at", when_used="json")
    def serialize_registration_datetimes(self, value: datetime | None) -> str | None:
        return utc_iso(value)


class AttendanceConfirmationResponse(BaseModel):
    id: UUID
    registration_id: UUID
    participant_name: str
    participant_code: str
    role: ParticipantRole
    status: AttendanceStatus
    checked_in_at: datetime

    @field_serializer("checked_in_at", when_used="json")
    def serialize_checked_in_at(self, value: datetime) -> str | None:
        return utc_iso(value)


class AttendanceRowResponse(BaseModel):
    registration_id: UUID
    training_id: UUID
    training_title: str
    trainer_name: str
    scheduled_at: datetime
    location: str
    participant_name: str
    participant_code: str
    role: ParticipantRole
    email: str | None
    phone: str | None
    joined_at: datetime
    attendance_status: str
    checked_in_at: datetime | None

    @field_serializer("scheduled_at", "joined_at", "checked_in_at", when_used="json")
    def serialize_attendance_datetimes(self, value: datetime | None) -> str | None:
        return utc_iso(value)


class TrainerOptionResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
