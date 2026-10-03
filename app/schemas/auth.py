"""Authentication request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

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
    branch_id: str | None = Field(default=None, max_length=50)
    department: str | None = Field(default=None, max_length=100)


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
