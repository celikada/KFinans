"""Tarihsel TCMB döviz kuru cache tablosu (daily_rates).

Belirli bir tarihteki 1 birim döviz = X TL kurunu saklar. PK (rate_date,
currency). TRY saklanmaz (=1 sabit). Yalnız gerçek TCMB yayın günleri tutulur;
forward-fill lookup'ta dinamik yapılır.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_rates",
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_to_try", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(length=16), server_default="tcmb", nullable=False),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rate_date", "currency", name="pk_daily_rates"),
    )


def downgrade() -> None:
    op.drop_table("daily_rates")
