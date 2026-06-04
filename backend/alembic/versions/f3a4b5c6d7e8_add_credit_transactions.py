"""Faz 3 kredi sistemi: credit_transactions ledger tablosu.

Her kredi bakiye degisiminin (yukleme + tuketim) audit-trail kaydi.
`users.credit_balance` denormalize anlik bakiye; bu tablo ona giden hareketler.

Kolonlar:
  id              UUID PK
  user_id         UUID FK -> users.id, ON DELETE RESTRICT (TTK m.82, 10 yil saklama)
  amount          INT NOT NULL  — pozitif: yukleme, negatif: tuketim
  reason          TEXT NOT NULL — 'purchase', 'ai_advice_medium', vb.
  reference_id    TEXT NULL     — iyzico paymentId / advice UUID
  idempotency_key VARCHAR(128) UNIQUE NULL — webhook cift-teslimat korumasi
  extra           JSONB NULL    — esnek context
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()

Index'ler: user_id, created_at.

Down: drop_table.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_credit_transactions_idempotency_key"),
    )
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])
    op.create_index("ix_credit_transactions_created_at", "credit_transactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_credit_transactions_created_at", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
