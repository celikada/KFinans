"""add bes_holdings table

Revision ID: 1f2e3d4c5b6a
Revises: 9a8b7c6d5e4f
Create Date: 2026-05-01 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "1f2e3d4c5b6a"
down_revision = "9a8b7c6d5e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bes_holdings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_name", sa.Text(), nullable=False),
        sa.Column("total_value_tl", sa.Numeric(18, 2), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bes_holdings_user_id", "bes_holdings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bes_holdings_user_id", "bes_holdings")
    op.drop_table("bes_holdings")
