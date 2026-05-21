"""expenses + planned_expenses: credit_card_id + is_paid

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-06

İki tabloya yeni alanlar:
- credit_card_id: opsiyonel kredi kartı bağlantısı (FK, ON DELETE SET NULL).
  Boşsa nakit veya banka transferi sayılır.
- is_paid: harcama gerçekleşti mi?
  - expenses default = TRUE (zaten yapılmış kayıt)
  - planned_expenses default = FALSE (planlı, henüz yapılmadı)

Çift sayım kuralı (sonraki adım — d):
- credit_card_id dolu + is_paid=true → kart borcuyla zaten sayıldı, gider'e
  DAHİL EDİLMEZ.
- diğer kombinasyonlarda DAHİL EDİLİR.
"""

import sqlalchemy as sa

from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # expenses
    op.add_column(
        "expenses",
        sa.Column("credit_card_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_expenses_credit_card_id",
        "expenses",
        "credit_cards",
        ["credit_card_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_expenses_credit_card_id", "expenses", ["credit_card_id"])
    op.add_column(
        "expenses",
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # planned_expenses
    op.add_column(
        "planned_expenses",
        sa.Column("credit_card_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_planned_expenses_credit_card_id",
        "planned_expenses",
        "credit_cards",
        ["credit_card_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_planned_expenses_credit_card_id",
        "planned_expenses",
        ["credit_card_id"],
    )
    op.add_column(
        "planned_expenses",
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("planned_expenses", "is_paid")
    op.drop_index("ix_planned_expenses_credit_card_id", table_name="planned_expenses")
    op.drop_constraint("fk_planned_expenses_credit_card_id", "planned_expenses", type_="foreignkey")
    op.drop_column("planned_expenses", "credit_card_id")

    op.drop_column("expenses", "is_paid")
    op.drop_index("ix_expenses_credit_card_id", table_name="expenses")
    op.drop_constraint("fk_expenses_credit_card_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "credit_card_id")
