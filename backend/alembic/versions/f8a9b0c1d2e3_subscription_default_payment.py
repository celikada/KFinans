"""Abonelik varsayılan ödeme: subscriptions.default_payment_method + default_credit_card_id.

Fatura kredi kartıyla ödendiğinde hangi kart kullanıldıysa aboneliğe varsayılan olarak
kaydedilir → sonraki fatura ödemesinde ön-seçili gelir (kullanıcı kolaylığı).
default_credit_card_id FK credit_cards (ON DELETE SET NULL — kart silinirse varsayılan düşer).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("default_payment_method", sa.String(12), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("default_credit_card_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_subscriptions_default_credit_card_id",
        "subscriptions",
        "credit_cards",
        ["default_credit_card_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_subscriptions_default_credit_card_id", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "default_credit_card_id")
    op.drop_column("subscriptions", "default_payment_method")
