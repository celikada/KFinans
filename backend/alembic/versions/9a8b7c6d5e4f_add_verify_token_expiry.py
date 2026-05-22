"""add verify_token_expires_at to users + verify_token index

Revision ID: 9a8b7c6d5e4f
Revises: f6a7b8c9d0e1
Create Date: 2026-04-30 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "9a8b7c6d5e4f"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("verify_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_users_verify_token", "users", ["verify_token"])


def downgrade() -> None:
    op.drop_index("ix_users_verify_token", "users")
    op.drop_column("users", "verify_token_expires_at")
