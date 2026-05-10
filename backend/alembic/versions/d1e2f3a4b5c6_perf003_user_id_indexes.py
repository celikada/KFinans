"""PERF-003 (FAZ H): Faz 3 tablolarinda user_id index'leri.

Onceki: PostgreSQL FK kolonu otomatik index olusturmaz; 7 Faz 3 tablosunda
user-scope sorgular (\"SELECT * FROM expenses WHERE user_id = ?\") sequential
scan yapar.

Yeni: ix_<table>_user_id single-col index (ix_expenses_user_id vs.).
Composite (user_id, date) gerekirse ileride; defensive yaklasimla single
col yeterli (PostgreSQL planner ek WHERE klozlari icin filter operatoru
ekler).

NOT: bes_holdings, cash_holdings, manual_crypto_holdings (user_exchange
composite), audit_logs (user_created composite), tefas/stock_holdings, vs.
zaten index'li (kendi migration'larinda eklendi). Bu migration sadece
eksiklikleri kapatir.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


# (table, index_name) — DB'de pg_indexes ile dogrulanmis 3 eksik tablo.
# Diger 9 (commodity_holdings, credit_cards, planned_expenses, recurring_incomes,
# bes/cash/manual_crypto, tefas/stock/integrations/wallet_addresses, advice,
# audit_logs composite) kendi migration'larinda zaten index'lendi.
_INDEXES = [
    ("expenses", "ix_expenses_user_id"),
    ("incomes", "ix_incomes_user_id"),
    ("budgets", "ix_budgets_user_id"),
]


def upgrade() -> None:
    for table, idx in _INDEXES:
        op.create_index(idx, table, ["user_id"])


def downgrade() -> None:
    for table, idx in _INDEXES:
        op.drop_index(idx, table_name=table)
