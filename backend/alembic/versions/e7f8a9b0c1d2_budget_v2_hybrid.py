"""Bütçe v2 (hibrit): budget_lines + budget_settings + budget_month_notes + personal_debts.

Mevcut veriyi (expenses/income/planned) kaynak alan birleşik planlama katmanı:
- budget_lines: her (kategori, yıl, ay) için ayrı planlanan tutar (12 aylık ızgara).
- budget_settings: 3-kova (Fundamental/Fun/Future You) hedef oranları + kategori→kova override.
- budget_month_notes: aylık serbest "analiz" + "aksiyon planı".
- personal_debts: kredi kartı dışı kişisel borç/alacak.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "month", "category", name="uq_budget_line_period_cat"),
    )
    op.create_index("ix_budget_lines_user_id", "budget_lines", ["user_id"])

    op.create_table(
        "budget_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fundamental_ratio", sa.Numeric(5, 4), server_default="0.5", nullable=False),
        sa.Column("fun_ratio", sa.Numeric(5, 4), server_default="0.3", nullable=False),
        sa.Column("future_ratio", sa.Numeric(5, 4), server_default="0.2", nullable=False),
        sa.Column("category_buckets", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "budget_month_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("action_plan", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "month", name="uq_budget_note_period"),
    )
    op.create_index("ix_budget_month_notes_user_id", "budget_month_notes", ["user_id"])

    op.create_table(
        "personal_debts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counterparty", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="TRY", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("settled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_debts_user_id", "personal_debts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_personal_debts_user_id", table_name="personal_debts")
    op.drop_table("personal_debts")
    op.drop_index("ix_budget_month_notes_user_id", table_name="budget_month_notes")
    op.drop_table("budget_month_notes")
    op.drop_table("budget_settings")
    op.drop_index("ix_budget_lines_user_id", table_name="budget_lines")
    op.drop_table("budget_lines")
