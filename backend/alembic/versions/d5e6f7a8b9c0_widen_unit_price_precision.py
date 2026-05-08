"""FIN-018 (FAZ H): unit_price_tl Numeric(18,4) -> Numeric(28,10)

SHIB ~0.00001 USD ≈ 0.0004 TRY, PEPE ~0.000003 USD ≈ 0.0001 TRY.
Numeric(18,4) en kucuk 0.0001'i tutar; bunun altinda yuvarlama 0'a duser
ve buyuk miktarlar (1 milyar SHIB) snapshot'ta 0 TL veya 4x yanlis deger
olarak gorunur — gorunmez kayip riski.

Numeric(28,10) ile 0.0000000001 TRY hassasiyetine cikar (10 ondalik basamak)
ve toplam 28 basamak (~10^18 TRY ust limit) — kullanici tarafinda makul.

Etkilenen kolonlar:
- asset_positions.unit_price_tl (snapshot pozisyonu)
- manual_crypto_holdings.manual_unit_price_tl (kullanici manuel fiyat)

Geri donus (downgrade) kayip yaratir: 4 ondalik altindaki degerler trunc edilir.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asset_positions.unit_price_tl: 18,4 -> 28,10
    op.alter_column(
        "asset_positions",
        "unit_price_tl",
        existing_type=sa.Numeric(18, 4),
        type_=sa.Numeric(28, 10),
        existing_nullable=False,
    )

    # manual_crypto_holdings.manual_unit_price_tl: 18,6 -> 28,10
    # (asset_positions ile tutarli precision)
    op.alter_column(
        "manual_crypto_holdings",
        "manual_unit_price_tl",
        existing_type=sa.Numeric(18, 6),
        type_=sa.Numeric(28, 10),
        existing_nullable=True,  # nullable — auto/linked modunda bos
    )


def downgrade() -> None:
    # DIKKAT: 4 ondalik altindaki precision kayip olur
    op.alter_column(
        "manual_crypto_holdings",
        "manual_unit_price_tl",
        existing_type=sa.Numeric(28, 10),
        type_=sa.Numeric(18, 6),
        existing_nullable=True,
    )
    op.alter_column(
        "asset_positions",
        "unit_price_tl",
        existing_type=sa.Numeric(28, 10),
        type_=sa.Numeric(18, 4),
        existing_nullable=False,
    )
