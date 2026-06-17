"""Kredi kartı ekstresi kısmi ödeme: credit_card_statements.paid_amount.

NULL + paid_at set → tam ödeme (= statement_amount); < statement_amount → kısmi
(kalan kartın current_period_debt'ine taşınır + nakit-akışında o ay yalnız ödenen sayılır).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credit_card_statements",
        sa.Column("paid_amount", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("credit_card_statements", "paid_amount")
