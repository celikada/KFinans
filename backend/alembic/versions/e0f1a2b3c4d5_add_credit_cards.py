"""add credit_cards (kredi kartı tanımı + dönem içi borç)

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-05-06

Kredi kartı modülünün ilk parçası: kart tanımı + henüz ekstreye düşmemiş
'dönem içi borç' alanı. Ekstreler ve taksitler ayrı tablolarda izlenecek
(sonraki migration'lar).

Alanlar:
- name: kart için kullanıcı dostu ad (ör. 'Akbank Visa Wings')
- bank_name: opsiyonel banka adı
- last_4: opsiyonel son 4 hane (string, '1234' formatında)
- credit_limit: opsiyonel kredi limiti
- statement_day: kesim günü (1-28)
- payment_due_day: son ödeme günü (1-28)
- current_period_debt: dönem içi henüz ekstreye düşmemiş tutar (kullanıcı
  manuel günceller)
- notes: opsiyonel
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("bank_name", sa.String(60), nullable=True),
        sa.Column("last_4", sa.String(4), nullable=True),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=True),
        sa.Column("statement_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payment_due_day", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("current_period_debt", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_cards_user_id", "credit_cards", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_cards_user_id", table_name="credit_cards")
    op.drop_table("credit_cards")
