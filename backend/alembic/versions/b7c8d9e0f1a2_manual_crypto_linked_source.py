"""manual_crypto_holdings: linked_source + linked_id, gold_gram/silver_gram migrasyonu

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-05-05

price_source: 'auto' | 'manual' | 'linked'
linked_source: 'binance' | 'coingecko' | 'tefas' | 'commodity'
linked_id: hedef varlığın ID'si (örn. commodity:XAG, coingecko:bitcoin, tefas:AFA)

Mevcut veriler:
- 'gold_gram'   → 'linked' + linked_source='commodity' + linked_id='XAU'
- 'silver_gram' → 'linked' + linked_source='commodity' + linked_id='XAG'
"""

import sqlalchemy as sa

from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_crypto_holdings",
        sa.Column("linked_source", sa.String(20), nullable=True),
    )
    op.add_column(
        "manual_crypto_holdings",
        sa.Column("linked_id", sa.String(100), nullable=True),
    )

    # Mevcut gold_gram/silver_gram kayıtlarını yeni 'linked' moduna çevir
    op.execute("""
        UPDATE manual_crypto_holdings
           SET price_source = 'linked',
               linked_source = 'commodity',
               linked_id = 'XAU'
         WHERE price_source = 'gold_gram'
    """)
    op.execute("""
        UPDATE manual_crypto_holdings
           SET price_source = 'linked',
               linked_source = 'commodity',
               linked_id = 'XAG'
         WHERE price_source = 'silver_gram'
    """)


def downgrade() -> None:
    # Linked + commodity:XAU/XAG kayıtlarını geri çevir
    op.execute("""
        UPDATE manual_crypto_holdings
           SET price_source = 'gold_gram',
               linked_source = NULL,
               linked_id = NULL
         WHERE price_source = 'linked'
           AND linked_source = 'commodity'
           AND linked_id = 'XAU'
    """)
    op.execute("""
        UPDATE manual_crypto_holdings
           SET price_source = 'silver_gram',
               linked_source = NULL,
               linked_id = NULL
         WHERE price_source = 'linked'
           AND linked_source = 'commodity'
           AND linked_id = 'XAG'
    """)
    op.drop_column("manual_crypto_holdings", "linked_id")
    op.drop_column("manual_crypto_holdings", "linked_source")
