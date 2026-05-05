"""incomes.recurring_income_id ekle (realize linki)

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-05-05

Periyodik gelir kayıtlarını "gerçekleşti" olarak işaretlerken üretilen
income kaydı, kaynak recurring_income'a bu kolonla bağlanır. Aynı recurring
+ ay-yıl kombinasyonu için çift kayıt unique constraint ile engellenir.

Periyodik kayıt silinirse: ON DELETE SET NULL (income kaydı kalır,
sadece bağlantı kopar).
"""

from alembic import op
import sqlalchemy as sa

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incomes",
        sa.Column("recurring_income_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_incomes_recurring_income_id",
        "incomes", "recurring_incomes",
        ["recurring_income_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_incomes_recurring_income_id",
        "incomes",
        ["recurring_income_id"],
    )
    # Aynı recurring + ay-yıl için çift realize'ı engelle (date_trunc ay bazlı)
    op.create_unique_constraint(
        "uq_incomes_recurring_month",
        "incomes",
        ["recurring_income_id", "date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_incomes_recurring_month", "incomes", type_="unique")
    op.drop_index("ix_incomes_recurring_income_id", table_name="incomes")
    op.drop_constraint("fk_incomes_recurring_income_id", "incomes", type_="foreignkey")
    op.drop_column("incomes", "recurring_income_id")
