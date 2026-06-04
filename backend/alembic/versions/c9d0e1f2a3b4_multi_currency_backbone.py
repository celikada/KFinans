"""Çoklu para birimi omurgası (v0.3.0).

Gelir/gider/planlı/periyodik/bütçe/kredi-kartı + user.default_currency için
para birimi alanları. Hibrit kur:
- income/expense: currency + amount_tl (işlem-anı kuru ile SABİT) + exchange_rate.
- planned_expense/recurring_income/budget/credit_card(+statement+installment):
  sadece currency (güncel kurla hesapta çevrilir, amount_tl yok).
- user: default_currency (yeni kayıt formlarında varsayılan).

Tüm kolonlar server_default="TRY" / "0" ile — mevcut kayıtlar geriye uyumlu:
TRY + amount_tl=amount varsayılır (veri kaybı yok). income/expense için eski
TRY kayıtlarda amount_tl=amount UPDATE edilir.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- income / expense: currency + amount_tl (SABİT) + exchange_rate ---
    for table in ("incomes", "expenses"):
        op.add_column(
            table,
            sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False),
        )
        op.add_column(
            table,
            sa.Column("amount_tl", sa.Numeric(18, 2), server_default="0", nullable=False),
        )
        op.add_column(
            table,
            sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True),
        )
        # Mevcut (TRY) kayıtlar: amount_tl = amount (1:1). server_default 0 ile
        # eklendi; eski satırlar TL bazlıydı, bu yüzden TL karşılığı = amount.
        op.execute(f"UPDATE {table} SET amount_tl = amount WHERE amount_tl = 0")  # noqa: S608

    # --- planned_expense / recurring_income / budget: sadece currency ---
    for table in ("planned_expenses", "recurring_incomes", "budgets"):
        op.add_column(
            table,
            sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False),
        )

    # --- credit_card + statement + installment: sadece currency ---
    for table in ("credit_cards", "credit_card_statements", "credit_card_installments"):
        op.add_column(
            table,
            sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False),
        )

    # --- user.default_currency ---
    op.add_column(
        "users",
        sa.Column("default_currency", sa.String(length=3), server_default="TRY", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "default_currency")

    for table in ("credit_card_installments", "credit_card_statements", "credit_cards"):
        op.drop_column(table, "currency")

    for table in ("budgets", "recurring_incomes", "planned_expenses"):
        op.drop_column(table, "currency")

    for table in ("expenses", "incomes"):
        op.drop_column(table, "exchange_rate")
        op.drop_column(table, "amount_tl")
        op.drop_column(table, "currency")
