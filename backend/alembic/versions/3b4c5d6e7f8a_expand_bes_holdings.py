"""expand bes_holdings: split total_value_tl into 4 metrics + contract_number

Revision ID: 3b4c5d6e7f8a
Revises: 2a3b4c5d6e7f
Create Date: 2026-05-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "3b4c5d6e7f8a"
down_revision = "2a3b4c5d6e7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 4 ana metrik: yatirilan ana para + getirisi, devlet katkisi + getirisi
    op.add_column("bes_holdings", sa.Column("contract_number", sa.Text(), nullable=True))
    op.add_column("bes_holdings", sa.Column("paid_principal", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("bes_holdings", sa.Column("paid_returns", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("bes_holdings", sa.Column("govt_contribution", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("bes_holdings", sa.Column("govt_returns", sa.Numeric(18, 2), nullable=False, server_default="0"))

    # Mevcut total_value_tl'yi paid_principal'a tasi (geri donuk uyumluluk),
    # sonra eski kolonu dusur.
    op.execute("UPDATE bes_holdings SET paid_principal = total_value_tl WHERE total_value_tl > 0")
    op.drop_column("bes_holdings", "total_value_tl")


def downgrade() -> None:
    op.add_column("bes_holdings", sa.Column("total_value_tl", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.execute(
        "UPDATE bes_holdings SET total_value_tl = "
        "paid_principal + paid_returns + govt_contribution + govt_returns"
    )
    op.drop_column("bes_holdings", "govt_returns")
    op.drop_column("bes_holdings", "govt_contribution")
    op.drop_column("bes_holdings", "paid_returns")
    op.drop_column("bes_holdings", "paid_principal")
    op.drop_column("bes_holdings", "contract_number")
