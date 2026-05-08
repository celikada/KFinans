"""AI-002 (FAZ H): investment_advice + cache_read_tokens, cache_creation_tokens

Anthropic prompt caching token metriklerini kalici saklamak icin 2 yeni
nullable INT kolonu. Cache hit orani analizi (maliyet tasarrufu izleme).

cache_read_tokens > 0 ise: system prompt cache HIT, %90 oranda daha ucuz.
cache_creation_tokens > 0 ise: ilk istek, cache yazildi (bir defalik bedel).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investment_advice",
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "investment_advice",
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investment_advice", "cache_creation_tokens")
    op.drop_column("investment_advice", "cache_read_tokens")
