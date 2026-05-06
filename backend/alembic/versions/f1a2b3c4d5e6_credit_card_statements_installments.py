"""add credit_card_statements + credit_card_installments

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-05-06

İki yeni tablo:
- credit_card_statements: her kart için aylık ekstre kayıtları
  (period_year, period_month, statement_amount, statement_date, due_date,
   paid_at). Aynı kart + ay-yıl için unique constraint.
- credit_card_installments: gelecek aylar için bilinen taksit yükümlülükleri
  (description, total_amount, monthly_amount, installments_total,
   installments_remaining, first_due_date). Cash flow projeksiyonunda
   kullanılacak.

Her ikisi de credit_cards.id'ye FK CASCADE — kart silinince temizlenir.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aylık ekstreler
    op.create_table(
        "credit_card_statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("statement_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["card_id"], ["credit_cards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_id", "period_year", "period_month", name="uq_statement_card_period"),
    )
    op.create_index("ix_credit_card_statements_card_id", "credit_card_statements", ["card_id"])

    # Gelecek taksitler
    op.create_table(
        "credit_card_installments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("monthly_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("installments_total", sa.Integer(), nullable=False),
        sa.Column("installments_remaining", sa.Integer(), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["card_id"], ["credit_cards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_card_installments_card_id", "credit_card_installments", ["card_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_card_installments_card_id", table_name="credit_card_installments")
    op.drop_table("credit_card_installments")
    op.drop_index("ix_credit_card_statements_card_id", table_name="credit_card_statements")
    op.drop_table("credit_card_statements")
