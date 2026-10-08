"""Track one-hour training reminder delivery.

Revision ID: c19e72a154bd
Revises: b04f6c8d21aa
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "c19e72a154bd"
down_revision = "b04f6c8d21aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trainings", sa.Column("trainer_reminder_sent_at", sa.DateTime(), nullable=True))
    op.add_column(
        "training_registrations",
        sa.Column("reminder_sent_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("training_registrations", "reminder_sent_at")
    op.drop_column("trainings", "trainer_reminder_sent_at")
