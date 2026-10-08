"""Enforce unique user and programme participant identities.

Revision ID: b04f6c8d21aa
Revises: 8c12a7e4b901
Create Date: 2026-10-08
"""

from alembic import op

revision = "b04f6c8d21aa"
down_revision = "8c12a7e4b901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Canonicalize legacy values before enforcing uniqueness. When older data
    # reused an identifier, retain it on the earliest account and clear it on
    # later accounts so no identity is arbitrarily reassigned.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            UPDATE users
            SET phone_number = CASE
                WHEN regexp_replace(phone_number, '[^0-9+]', '', 'g') ~ '^0[0-9]{9}$'
                    THEN '+254' || substring(regexp_replace(phone_number, '[^0-9]', '', 'g') FROM 2)
                WHEN regexp_replace(phone_number, '[^0-9+]', '', 'g') ~ '^254[0-9]{9}$'
                    THEN '+' || regexp_replace(phone_number, '[^0-9]', '', 'g')
                ELSE regexp_replace(phone_number, '[^0-9+]', '', 'g')
            END
            WHERE phone_number IS NOT NULL
            """
        )
        op.execute(
            """
            UPDATE users
            SET employee_id = upper(trim(employee_id))
            WHERE employee_id IS NOT NULL
            """
        )
        op.execute(
            """
            UPDATE users
            SET agent_code = upper(trim(agent_code))
            WHERE agent_code IS NOT NULL
            """
        )
        op.execute(
            """
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY phone_number ORDER BY created_at, id
                ) AS duplicate_rank
                FROM users
                WHERE phone_number IS NOT NULL
            )
            UPDATE users
            SET phone_number = NULL
            FROM ranked
            WHERE users.id = ranked.id AND ranked.duplicate_rank > 1
            """
        )
        op.execute(
            """
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY employee_id ORDER BY created_at, id
                ) AS duplicate_rank
                FROM users
                WHERE employee_id IS NOT NULL
            )
            UPDATE users
            SET employee_id = NULL
            FROM ranked
            WHERE users.id = ranked.id AND ranked.duplicate_rank > 1
            """
        )
        op.execute(
            """
            UPDATE training_registrations
            SET participant_code = upper(trim(participant_code)),
                email = lower(trim(email)),
                phone = CASE
                    WHEN regexp_replace(phone, '[^0-9+]', '', 'g') ~ '^0[0-9]{9}$'
                        THEN '+254' || substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 2)
                    WHEN regexp_replace(phone, '[^0-9+]', '', 'g') ~ '^254[0-9]{9}$'
                        THEN '+' || regexp_replace(phone, '[^0-9]', '', 'g')
                    ELSE regexp_replace(phone, '[^0-9+]', '', 'g')
                END
            """
        )

    op.create_index(
        "ix_users_phone_number",
        "users",
        ["phone_number"],
        unique=True,
    )
    op.drop_index("ix_users_employee_id", table_name="users")
    op.create_index(
        "ix_users_employee_id",
        "users",
        ["employee_id"],
        unique=True,
    )

    op.drop_constraint(
        "uq_training_registration_identity",
        "training_registrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_training_registration_identity",
        "training_registrations",
        ["training_id", "participant_code"],
    )
    op.create_unique_constraint(
        "uq_training_registration_phone",
        "training_registrations",
        ["training_id", "phone"],
    )
    op.create_unique_constraint(
        "uq_training_registration_email",
        "training_registrations",
        ["training_id", "email"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_training_registration_email",
        "training_registrations",
        type_="unique",
    )
    op.drop_constraint(
        "uq_training_registration_phone",
        "training_registrations",
        type_="unique",
    )
    op.drop_constraint(
        "uq_training_registration_identity",
        "training_registrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_training_registration_identity",
        "training_registrations",
        ["training_id", "role", "participant_code"],
    )

    op.drop_index("ix_users_employee_id", table_name="users")
    op.create_index(
        "ix_users_employee_id",
        "users",
        ["employee_id"],
        unique=False,
    )
    op.drop_index("ix_users_phone_number", table_name="users")
