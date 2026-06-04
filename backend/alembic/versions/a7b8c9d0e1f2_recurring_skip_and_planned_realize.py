"""Periyodik gerçekleşme: recurring_skips + expenses.planned_expense_id.

İki ekleme:
1. `recurring_skips` — periyodik gelir/gider için dönem-bazlı 'gerçekleşmeyecek'
   işareti (kind + ref_id polimorfik referans + period). Popup pending hesabında
   o dönemi bir daha sormamak için.
2. `expenses.planned_expense_id` — periyodik giderin (planned_expense) o dönem
   için gerçekleştiği gider kaydının kaynağı (gelir↔income simetrisi). Çift
   realize'ı engelleyen partial unique index (planned_expense_id, date).

Down: index + kolon + tablo geri alınır.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) recurring_skips
    op.create_table(
        "recurring_skips",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "ref_id",
            "period_year",
            "period_month",
            name="uq_recurring_skip_period",
        ),
    )
    op.create_index("ix_recurring_skips_user_id", "recurring_skips", ["user_id"])

    # 2) expenses.planned_expense_id + partial unique index (çift realize engeli)
    op.add_column("expenses", sa.Column("planned_expense_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_expenses_planned_expense_id",
        "expenses",
        "planned_expenses",
        ["planned_expense_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_expenses_planned_expense_id", "expenses", ["planned_expense_id"])
    op.create_index(
        "uq_expense_planned_period",
        "expenses",
        ["planned_expense_id", "date"],
        unique=True,
        postgresql_where=sa.text("planned_expense_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_expense_planned_period", table_name="expenses")
    op.drop_index("ix_expenses_planned_expense_id", table_name="expenses")
    op.drop_constraint("fk_expenses_planned_expense_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "planned_expense_id")
    op.drop_index("ix_recurring_skips_user_id", table_name="recurring_skips")
    op.drop_table("recurring_skips")
