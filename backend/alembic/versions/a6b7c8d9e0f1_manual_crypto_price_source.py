"""manual_crypto_holdings'a price_source + manual_unit_price_tl

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-05-05

price_source: 'auto' | 'manual' | 'gold_gram' | 'silver_gram'
- auto: Binance USDT + CoinGecko fallback (mevcut davranış)
- manual: kullanıcı manual_unit_price_tl alanına TL/adet girer
- gold_gram: commodity servisten anlık altın gr fiyatı (TRY/g)
- silver_gram: commodity servisten anlık gümüş gr fiyatı (TRY/g)
"""

from alembic import op
import sqlalchemy as sa

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_crypto_holdings",
        sa.Column("price_source", sa.String(20), nullable=False, server_default="auto"),
    )
    op.add_column(
        "manual_crypto_holdings",
        sa.Column("manual_unit_price_tl", sa.Numeric(18, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manual_crypto_holdings", "manual_unit_price_tl")
    op.drop_column("manual_crypto_holdings", "price_source")
