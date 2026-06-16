"""Abonelik v2 alanları: start_date + next_bill/due_date + bill_no.

start_date: bütçenin forecast/planlı-gider olarak sayılmaya başladığı tarih.
next_bill_date/next_due_date: PDF fatura import'tan gelen sonraki dönem hatırlatması.
subscription_bills.bill_no: import edilen faturanın no'su (referans).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # start_date NOT NULL — mevcut kayıtlar server_default (bugün) ile dolar.
    op.add_column(
        "subscriptions",
        sa.Column("start_date", sa.Date(), server_default=sa.func.current_date(), nullable=False),
    )
    op.add_column("subscriptions", sa.Column("next_bill_date", sa.Date(), nullable=True))
    op.add_column("subscriptions", sa.Column("next_due_date", sa.Date(), nullable=True))
    op.add_column("subscription_bills", sa.Column("bill_no", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("subscription_bills", "bill_no")
    op.drop_column("subscriptions", "next_due_date")
    op.drop_column("subscriptions", "next_bill_date")
    op.drop_column("subscriptions", "start_date")
