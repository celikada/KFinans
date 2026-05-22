"""users tablosuna email_verified, verify_token, deleted_at, credit_balance kolonlari ekle

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-29 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("verify_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("users", sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_users_credit_balance_nonnegative", "users", "credit_balance >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_users_credit_balance_nonnegative", "users", type_="check")
    op.drop_column("users", "credit_balance")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "verify_token")
    op.drop_column("users", "email_verified")
