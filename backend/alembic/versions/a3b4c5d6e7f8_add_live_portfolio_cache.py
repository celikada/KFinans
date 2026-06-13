"""Kullanıcı başına canlı portföy cache tablosu (live_portfolio_cache).

Ağır/dış-API portföy verisi arka planda hesaplanıp burada saklanır; dashboard +
detay sayfaları hızlı DB okumasıyla alır (her açılışta dış çağrı yapmaz). user_id
PK → kullanıcı başına tek satır (UPSERT). Snapshot'tan ayrı (mutable şu-anki görünüm).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_portfolio_cache",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("total_value_tl", sa.Numeric(18, 2), nullable=True),
        sa.Column("rates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("health_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="ok", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("refreshed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name="pk_live_portfolio_cache"),
    )


def downgrade() -> None:
    op.drop_table("live_portfolio_cache")
