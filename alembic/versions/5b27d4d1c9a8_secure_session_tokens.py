"""Add revocation metadata and remove plaintext OTP storage.

Revision ID: 5b27d4d1c9a8
Revises: 1b6ebdd051d6
Create Date: 2026-09-26
"""

import sqlalchemy as sa

from alembic import op

revision = "5b27d4d1c9a8"
down_revision = "1b6ebdd051d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("last_used_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("otps") as batch_op:
        batch_op.drop_column("code")


def downgrade() -> None:
    with op.batch_alter_table("otps") as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=10), nullable=False, server_default=""))

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("last_used_at")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("token_version")
