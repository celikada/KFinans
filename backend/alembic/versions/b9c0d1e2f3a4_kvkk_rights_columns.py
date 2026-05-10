"""COMP-003 + COMP-006 + COMP-029 (FAZ H): KVKK haklari kolonlari.

users tablosuna 5 yeni kolon:
  - overseas_consent_at: KVKK m.5/1 ispat yuku — kullanici acik rizasini
    register'da verdiginde timestamp; revoke edilince NULL.
  - terms_accepted_at, kvkk_read_at: ileride Kullanim Sartlari /
    KVKK Aydinlatma Metni revize edildiginde re-accept zorunlu kilmak icin.
  - email_change_new: yeni email hedefi (verification beklenirken bekler)
  - email_change_token: dogrulama token'i (URL-safe, 1 saat TTL)
  - email_change_expires_at: token TTL
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("overseas_consent_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("users", sa.Column("terms_accepted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("users", sa.Column("kvkk_read_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("users", sa.Column("email_change_new", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("email_change_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("email_change_expires_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_index("ix_users_email_change_token", "users", ["email_change_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_email_change_token", table_name="users")
    op.drop_column("users", "email_change_expires_at")
    op.drop_column("users", "email_change_token")
    op.drop_column("users", "email_change_new")
    op.drop_column("users", "kvkk_read_at")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "overseas_consent_at")
