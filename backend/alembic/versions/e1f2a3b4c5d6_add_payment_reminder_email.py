"""Ödeme hatırlatması e-postası opt-in alanı.

users tablosuna `payment_reminder_email` (Boolean, server default False).
Push bildirimine alternatif; her gün ödemesi yaklaşan kredi kartı borçları
için opt-in + email_verified kullanıcılara Resend ile e-posta gönderilir.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("payment_reminder_email", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "payment_reminder_email")
