"""Base model mixins for common functionality."""

from datetime import UTC, datetime

from sqlmodel import Field


def naive_utcnow() -> datetime:
    """Return UTC without tzinfo for the existing timestamp column contract."""

    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: datetime = Field(
        default_factory=naive_utcnow,
        nullable=False,
        index=True,
    )
    updated_at: datetime = Field(
        default_factory=naive_utcnow,
        nullable=False,
        index=True,
        sa_column_kwargs={"onupdate": naive_utcnow},
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    deleted_at: datetime | None = Field(
        default=None,
        nullable=True,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete the record."""
        self.deleted_at = naive_utcnow()

    def restore(self) -> None:
        """Restore soft deleted record."""
        self.deleted_at = None
