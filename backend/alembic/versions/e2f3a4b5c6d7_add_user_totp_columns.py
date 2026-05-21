"""MFA TOTP (audit #5 MFA): user.totp_secret + totp_enabled + totp_recovery_codes.

RFC 6238 (TOTP) ile Google Authenticator / Authy / 1Password / Microsoft
Authenticator uyumlu iki faktor. Tum kolonlar nullable / default-False —
mevcut kullanicilar bos basla, opt-in.

Kolonlar:
  totp_secret           Text NULL      — Fernet ciphertext (plaintext base32 secret)
  totp_enabled          Boolean NOT NULL DEFAULT false — setup -> enable arasi
                        gecici durumda hala False; verify basarili olduktan
                        sonra True'ya gecer.
  totp_recovery_codes   Text NULL      — JSON list[str] bcrypt-hashed kodlar

Index gerekmez: totp_* kolonlari sadece self-user context'inde okunur
(WHERE id = current_user.id zaten PK lookup).

Down: 3 kolonu drop eder. Setup yapmis kullanicilar verilerini kaybeder
(beklenen davranis — rollback'te zaten MFA flow yok).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("users", sa.Column("totp_recovery_codes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "totp_recovery_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
