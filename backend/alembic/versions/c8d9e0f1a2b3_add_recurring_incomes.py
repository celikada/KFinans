"""add recurring_incomes (periyodik gelir tahmini — maaş, kira vb.)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-05-05

planned_expenses ile aynı yapıda; gelir tarafı için tahmini periyodik
kayıtları tutar. Tek seferlik gelirler 'incomes' tablosunda kalmaya devam
eder; bu tablo sadece beklenti hesaplamalarında kullanılır.

category: salary | rental | dividend | bonus | freelance | other
recurrence: one_time | monthly | quarterly | biannual | yearly | custom
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_incomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("recurrence", sa.String(20), nullable=False),
        sa.Column("months", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("day_of_month", sa.Integer(), server_default="1", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_incomes_user_id", "recurring_incomes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recurring_incomes_user_id", table_name="recurring_incomes")
    op.drop_table("recurring_incomes")
