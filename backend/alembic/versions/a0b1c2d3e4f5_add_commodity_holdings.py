"""add commodity holdings

Revision ID: a0b1c2d3e4f5
Revises: 9b0c1d2e3f4a
Create Date: 2026-05-03
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "9b0c1d2e3f4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commodity_holdings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # unit_type: "gram" | "biga" | "coin"
        sa.Column("unit_type", sa.String(10), nullable=False),
        # metal: "gold" | "silver"  — coin türleri için her zaman "gold"
        sa.Column("metal", sa.String(10), nullable=False),
        # biga_code: A01..A08, G01..G07 — sadece unit_type="biga" için
        sa.Column("biga_code", sa.String(5), nullable=True),
        # coin_type: ceyrek|yarim|tam|cumhuriyet|resat|ata — sadece unit_type="coin" için
        sa.Column("coin_type", sa.String(20), nullable=True),
        # quantity: gram için gram, diğerleri için adet
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commodity_holdings_user_id", "commodity_holdings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_commodity_holdings_user_id", table_name="commodity_holdings")
    op.drop_table("commodity_holdings")
