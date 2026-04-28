"""add tefas_holdings table

Revision ID: a1b2c3d4e5f6
Revises: 876bd62e282c
Create Date: 2026-04-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "876bd62e282c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tefas_holdings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("tefas_holdings")
