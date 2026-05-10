"""AI-005 (FAZ H): Anthropic ozel acik riza kolonlari (KVKK m.9).

users tablosuna 2 yeni kolon:
  anthropic_consent_at: timestamp (riza tarihi); revoke -> NULL
  anthropic_consent_version: hangi metin versiyonuna riza verildi (ileride
    metin guncellendiginde re-accept zorunlu kilmak icin)

COMP-006'daki overseas_consent_at genel yurt disi aktarima bakar; bu kolonlar
**Anthropic API**'ye ozel — kullanici diger aktarimlari onayladigi halde
Anthropic'i reddedebilir.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("anthropic_consent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("anthropic_consent_version", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "anthropic_consent_version")
    op.drop_column("users", "anthropic_consent_at")
