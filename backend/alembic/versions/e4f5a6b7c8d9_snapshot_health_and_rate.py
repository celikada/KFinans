"""add health_issues + usd_try_rate to portfolio_snapshots

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # health_issues: snapshot anında 0 değer/hata veren kaynakların listesi
    # Format: [{"source": "ethereum", "code": "rpc_failed", "msg": "..."}]
    op.add_column(
        "portfolio_snapshots",
        sa.Column("health_issues", JSONB, nullable=True),
    )
    # usd_try_rate: snapshot anındaki TCMB USD/TRY kuru
    # Geçmiş grafiklerde USD görünümü için (anlık kur değil)
    op.add_column(
        "portfolio_snapshots",
        sa.Column("usd_try_rate", sa.Numeric(18, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_snapshots", "usd_try_rate")
    op.drop_column("portfolio_snapshots", "health_issues")
