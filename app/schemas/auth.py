"""Authentication request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.identity import normalize_person_name, normalize_personnel_code, normalize_phone_number
from app.models.enums import UserRole


class InitialAdminRegisterRequest(BaseModel):
    secret_key: str = Field(min_length=10)
    email: EmailStr
    password: str = Field(min_length=10)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class FirstTimePasswordChangeRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=256)
    confirm_password: str = Field(min_length=10, max_length=256)

    @model_validator(mode="after")
    def passwords_match(self) -> "FirstTimePasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)
    confirm_password: str = Field(min_length=10, max_length=256)

    @model_validator(mode="after")
    def validate_passwords(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from the current password")
        return self


class OTPSendRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=6, max_length=10)
    new_password: str = Field(min_length=10, max_length=256)
    confirm_password: str = Field(min_length=10, max_length=256)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordResetRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    phone_number: str | None = Field(default=None, max_length=20)
    employee_id: str | None = Field(default=None, max_length=50)
    agent_code: str | None = Field(default=None, max_length=20)
    branch_id: str | None = Field(default=None, max_length=50)
    department: str | None = Field(default=None, max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return normalize_person_name(value)

    @field_validator("phone_number")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        return normalize_phone_number(value) if value else None

    @field_validator("employee_id", "agent_code")
    @classmethod
    def valid_personnel_code(cls, value: str | None) -> str | None:
        return normalize_personnel_code(value) if value else None

    @field_validator("branch_id", "department")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        normalized = " ".join(value.strip().split()) if value else None
        return normalized or None

    @model_validator(mode="after")
    def required_identity_fields(self) -> "AdminCreateUserRequest":
        if not self.phone_number:
            raise ValueError("A valid phone number is required for every user")
        if self.role == UserRole.AGENT:
            self.agent_code = self.agent_code or self.employee_id
            self.employee_id = None
            if not self.agent_code:
                raise ValueError("Agent code is required for an agent")
        elif not self.employee_id:
            raise ValueError("Employee ID is required for this user role")
        return self


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    phone_number: str | None = None
    profile_pic_url: str | None = None
    is_active: bool
    is_email_verified: bool
    is_password_changed: bool
    employee_id: str | None = None
    branch_id: str | None = None
    department: str | None = None
    agent_code: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserResponse
