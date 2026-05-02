"""add monthly_expense_goal to users

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "6e7f8a9b0c1d"
down_revision = "5d6e7f8a9b0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("monthly_expense_goal", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "monthly_expense_goal")
