"""add manual_crypto_holdings (API'siz borsa hesapları için manuel giriş)

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_crypto_holdings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("exchange", sa.String(40), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("avg_cost_tl", sa.Numeric(18, 6), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_manual_crypto_holdings_user_exchange",
        "manual_crypto_holdings",
        ["user_id", "exchange"],
    )


def downgrade() -> None:
    op.drop_index("ix_manual_crypto_holdings_user_exchange", table_name="manual_crypto_holdings")
    op.drop_table("manual_crypto_holdings")
