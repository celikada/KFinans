"""add distributor (portföy yöneticisi/kurum) to tefas + stock holdings

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-03
"""

import sqlalchemy as sa

from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tefas_holdings",
        sa.Column("distributor", sa.String(50), nullable=True),
    )
    op.add_column(
        "stock_holdings",
        sa.Column("distributor", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tefas_holdings", "distributor")
    op.drop_column("stock_holdings", "distributor")
