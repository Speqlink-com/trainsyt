"""Add QR-powered training registration and attendance.

Revision ID: 8c12a7e4b901
Revises: 5b27d4d1c9a8
Create Date: 2026-09-30
"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision = "8c12a7e4b901"
down_revision = "5b27d4d1c9a8"
branch_labels = None
depends_on = None


training_status = sa.Enum(
    "SCHEDULED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
    name="trainingstatus",
)
participant_role = sa.Enum(
    "AGENT",
    "SALES_MANAGER",
    "HOA",
    "TRAINER",
    "ADMIN",
    "STAFF",
    "GUEST",
    name="participantrole",
)
attendance_status = sa.Enum(
    "PRESENT",
    "ABSENT",
    "LATE",
    "EXCUSED",
    name="attendancestatus",
)


def upgrade() -> None:
    op.create_table(
        "trainings",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_code", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=False),
        sa.Column("trainer_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=False),
        sa.Column("location", sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
        sa.Column("audience_roles", sa.JSON(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", training_status, nullable=False),
        sa.Column("attendance_open", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["trainer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trainings_attendance_open"), "trainings", ["attendance_open"])
    op.create_index(op.f("ix_trainings_created_at"), "trainings", ["created_at"])
    op.create_index(op.f("ix_trainings_created_by_id"), "trainings", ["created_by_id"])
    op.create_index(op.f("ix_trainings_public_code"), "trainings", ["public_code"], unique=True)
    op.create_index(op.f("ix_trainings_scheduled_at"), "trainings", ["scheduled_at"])
    op.create_index(op.f("ix_trainings_status"), "trainings", ["status"])
    op.create_index(op.f("ix_trainings_title"), "trainings", ["title"])
    op.create_index(op.f("ix_trainings_trainer_id"), "trainings", ["trainer_id"])
    op.create_index(op.f("ix_trainings_updated_at"), "trainings", ["updated_at"])

    op.create_table(
        "training_registrations",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("training_id", sa.Uuid(), nullable=False),
        sa.Column("participant_name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("participant_code", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("role", participant_role, nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.ForeignKeyConstraint(["training_id"], ["trainings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "training_id",
            "role",
            "participant_code",
            name="uq_training_registration_identity",
        ),
    )
    op.create_index(op.f("ix_training_registrations_created_at"), "training_registrations", ["created_at"])
    op.create_index(op.f("ix_training_registrations_email"), "training_registrations", ["email"])
    op.create_index(op.f("ix_training_registrations_joined_at"), "training_registrations", ["joined_at"])
    op.create_index(
        op.f("ix_training_registrations_participant_code"), "training_registrations", ["participant_code"]
    )
    op.create_index(
        op.f("ix_training_registrations_participant_name"), "training_registrations", ["participant_name"]
    )
    op.create_index(op.f("ix_training_registrations_role"), "training_registrations", ["role"])
    op.create_index(op.f("ix_training_registrations_training_id"), "training_registrations", ["training_id"])
    op.create_index(op.f("ix_training_registrations_updated_at"), "training_registrations", ["updated_at"])

    op.create_table(
        "training_attendance",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("training_id", sa.Uuid(), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("status", attendance_status, nullable=False),
        sa.Column("checked_in_at", sa.DateTime(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column("ip_address", sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True),
        sa.Column("user_agent", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.ForeignKeyConstraint(["registration_id"], ["training_registrations.id"]),
        sa.ForeignKeyConstraint(["training_id"], ["trainings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("registration_id", name="uq_training_attendance_registration"),
    )
    op.create_index(op.f("ix_training_attendance_checked_in_at"), "training_attendance", ["checked_in_at"])
    op.create_index(op.f("ix_training_attendance_created_at"), "training_attendance", ["created_at"])
    op.create_index(
        op.f("ix_training_attendance_registration_id"), "training_attendance", ["registration_id"]
    )
    op.create_index(op.f("ix_training_attendance_status"), "training_attendance", ["status"])
    op.create_index(op.f("ix_training_attendance_training_id"), "training_attendance", ["training_id"])
    op.create_index(op.f("ix_training_attendance_updated_at"), "training_attendance", ["updated_at"])


def downgrade() -> None:
    op.drop_table("training_attendance")
    op.drop_table("training_registrations")
    op.drop_table("trainings")
    if op.get_bind().dialect.name == "postgresql":
        attendance_status.drop(op.get_bind(), checkfirst=True)
        participant_role.drop(op.get_bind(), checkfirst=True)
        training_status.drop(op.get_bind(), checkfirst=True)
