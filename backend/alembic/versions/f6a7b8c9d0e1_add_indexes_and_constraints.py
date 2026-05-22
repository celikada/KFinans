"""Performans icin user_id index'leri ve integrations UNIQUE constraint ekle

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-29 00:00:00.000000
"""

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # integrations: ayni kullanici + saglayici icin tek kayit
    op.create_unique_constraint("uq_integrations_user_provider", "integrations", ["user_id", "provider"])

    # user_id filtre indeksleri (FK lookup hizlandirma)
    # ix_tefas_holdings_user_id ve ix_stock_holdings_user_id ilgili tablo migration'larinda
    # zaten olusturuldu — burada tekrar eklenmiyor.
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])
    op.create_index("ix_wallet_addresses_user_id", "wallet_addresses", ["user_id"])
    op.create_index("ix_investment_advice_user_id", "investment_advice", ["user_id"])

    # portfolio_snapshots: dashboard sorgulari user_id + snapshot_date DESC kombinasyonunu kullanir
    op.create_index(
        "ix_portfolio_snapshots_user_date",
        "portfolio_snapshots",
        ["user_id", "snapshot_date"],
    )

    # asset_positions: snapshot iliski yuklemesi icin
    op.create_index("ix_asset_positions_snapshot_id", "asset_positions", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_asset_positions_snapshot_id", "asset_positions")
    op.drop_index("ix_portfolio_snapshots_user_date", "portfolio_snapshots")
    op.drop_index("ix_investment_advice_user_id", "investment_advice")
    op.drop_index("ix_wallet_addresses_user_id", "wallet_addresses")
    op.drop_index("ix_integrations_user_id", "integrations")
    op.drop_constraint("uq_integrations_user_provider", "integrations", type_="unique")
