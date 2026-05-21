"""replace monthly_expense_goal with goal_amount + goal_currency

Revision ID: 7f8a9b0c1d2e
Revises: 6e7f8a9b0c1d
Create Date: 2026-05-03
"""

import sqlalchemy as sa

from alembic import op

revision = "7f8a9b0c1d2e"
down_revision = "6e7f8a9b0c1d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("goal_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column(
        "users", sa.Column("goal_currency", sa.String(3), nullable=False, server_default="TRY")
    )
    # Mevcut TRY degerini yeni alana tasiy
    op.execute(
        "UPDATE users SET goal_amount = monthly_expense_goal WHERE monthly_expense_goal IS NOT NULL"
    )
    op.drop_column("users", "monthly_expense_goal")


def downgrade() -> None:
    op.add_column("users", sa.Column("monthly_expense_goal", sa.Numeric(18, 2), nullable=True))
    op.execute("UPDATE users SET monthly_expense_goal = goal_amount WHERE goal_currency = 'TRY'")
    op.drop_column("users", "goal_currency")
    op.drop_column("users", "goal_amount")
