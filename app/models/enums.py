"""Enumeration types for training system models."""

from enum import Enum

# ============================================================================
# USER & AUTH ENUMS
# ============================================================================


class UserRole(str, Enum):
    """User roles in the training system."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    TRAINER = "trainer"
    SALES_MANAGER = "sales_manager"
    HOA = "hoa"  # Head of Agency
    AGENT = "agent"


class OTPPurpose(str, Enum):
    """OTP verification purposes."""

    LOGIN = "login"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"


# ============================================================================
# TRAINING ENUMS
# ============================================================================


class TrainingCategory(str, Enum):
    """Training categories."""

    NEW_AGENTS = "new_agents"
    POST_TRAINING = "post_training"
    EXISTING_TARGETED = "existing_targeted"
    BRANCH_TRAINING = "branch_training"
    SM_HOA_INDUCTION = "sm_hoa_induction"
    LEADERSHIP = "leadership"
    SPECIALISED = "specialised"
    ECOP = "ecop"
    PERSONAL_FINANCE = "personal_finance"
    ALTERNATIVE_DISTRIBUTION = "alternative_distribution"


class TrainingStatus(str, Enum):
    """Training session status."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttendanceStatus(str, Enum):
    """Training attendance status."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class ParticipantRole(str, Enum):
    """Roles accepted by the public QR registration flow."""

    AGENT = "agent"
    SALES_MANAGER = "sales_manager"
    HOA = "hoa"
    TRAINER = "trainer"
    ADMIN = "admin"
    STAFF = "staff"
    GUEST = "guest"


# ============================================================================
# ONBOARDING ENUMS
# ============================================================================


class OnboardingStage(str, Enum):
    """Onboarding stages for new joiners."""

    INTERVIEW = "interview"
    INVITATION_SENT = "invitation_sent"
    APTITUDE_TEST = "aptitude_test"
    REVIEW_TEST = "review_test"
    INDUCTION = "induction"
    AGENCY_SERVICES = "agency_services"
    ONBOARDING = "onboarding"
    AGENT_CODE = "agent_code"
    ACTIVE = "active"


class OnboardingStatus(str, Enum):
    """Status within each onboarding stage."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


# ============================================================================
# AGENT ENUMS
# ============================================================================


class AgentStatus(str, Enum):
    """Agent status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class ComplianceStatus(str, Enum):
    """Training compliance status."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"


# ============================================================================
# BRANCH/TERRITORY ENUMS
# ============================================================================


class BranchType(str, Enum):
    """Branch classification types."""

    REGIONAL = "regional"
    COUNTY = "county"
    BRANCH = "branch"
    SUB_BRANCH = "sub_branch"


# ============================================================================
# AUDIT ENUMS
# ============================================================================


class AuditAction(str, Enum):
    """Actions tracked in audit log."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    APPROVE = "approve"
    REJECT = "reject"
    ASSIGN = "assign"
    COMPLETE = "complete"
    CANCEL = "cancel"


class AuditEntityType(str, Enum):
    """Entity types for audit logging."""

    USER = "user"
    AGENT = "agent"
    TRAINING = "training"
    ATTENDANCE = "attendance"
    ONBOARDING = "onboarding"
    REPORT = "report"
