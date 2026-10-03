"""Schemas for training programmes and QR attendance."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import AttendanceStatus, ParticipantRole, TrainingStatus


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

    @field_validator("audience_roles")
    @classmethod
    def unique_roles(cls, value: list[ParticipantRole]) -> list[ParticipantRole]:
        return list(dict.fromkeys(value))


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
    participant_code: str = Field(min_length=2, max_length=100)
    role: ParticipantRole
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("participant_name", "participant_code")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str | None) -> str | None:
        stripped = value.strip() if value else None
        return stripped or None


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


class AttendanceConfirmationResponse(BaseModel):
    id: UUID
    registration_id: UUID
    participant_name: str
    participant_code: str
    role: ParticipantRole
    status: AttendanceStatus
    checked_in_at: datetime


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


class TrainerOptionResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
