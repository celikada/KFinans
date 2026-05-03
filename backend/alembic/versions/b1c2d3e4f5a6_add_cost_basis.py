"""add cost basis to stock and tefas holdings

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_holdings",
        sa.Column("avg_cost_tl", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "tefas_holdings",
        sa.Column("avg_cost_tl", sa.Numeric(18, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_holdings", "avg_cost_tl")
    op.drop_column("tefas_holdings", "avg_cost_tl")
