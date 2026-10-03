"""Models package for the training system."""

# Import all models to ensure they are registered with SQLModel
from app.models.base import SoftDeleteMixin, TimestampMixin
from app.models.enums import (
    AgentStatus,
    AttendanceStatus,
    AuditAction,
    AuditEntityType,
    BranchType,
    ComplianceStatus,
    OnboardingStage,
    OnboardingStatus,
    OTPPurpose,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
    UserRole,
)
from app.models.otp import OTP
from app.models.sessions import Session
from app.models.trainings import Training, TrainingAttendance, TrainingRegistration
from app.models.users import User

__all__ = [
    # Base
    "TimestampMixin",
    "SoftDeleteMixin",
    # Enums
    "UserRole",
    "OTPPurpose",
    "TrainingCategory",
    "TrainingStatus",
    "AttendanceStatus",
    "ParticipantRole",
    "OnboardingStage",
    "OnboardingStatus",
    "AgentStatus",
    "ComplianceStatus",
    "BranchType",
    "AuditAction",
    "AuditEntityType",
    # Models
    "User",
    "Session",
    "OTP",
    "Training",
    "TrainingRegistration",
    "TrainingAttendance",
]
