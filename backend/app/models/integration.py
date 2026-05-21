import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import address_fingerprint, decrypt_secret, encrypt_secret
from app.models.base import Base


class Integration(Base):
    """Exchange entegrasyonları — Binance, iCrypex, TEFAS, BES (API key ile)."""

    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # DBA-001 (FAZ H): User silinince integration cascade silinir; pg_dump restore'da
    # FK violation onlenir.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # binance | icrypex | tefas | bes
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_key: Mapped[Optional[str]] = mapped_column(Text)
    encrypted_secret: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="integrations")


class WalletAddress(Base):
    """Blockchain cüzdan adresleri — Fernet ile şifrelenmiş plaintext public key.

    Plaintext address asla DB'de tutulmaz. `address_encrypted` Fernet ciphertext;
    `address_fingerprint` SHA-256(lowercase address) lookup ve unique constraint
    için. `address` hybrid property transparent encrypt/decrypt sağlar — service
    ve API kodu wallet.address'i okur/yazar gibi davranır.
    """

    __tablename__ = "wallet_addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # DBA-001 (FAZ H): User silinince wallet cascade.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # ethereum | sonic | avalanche_c | avalanche_p | bitcoin | solana | cardano | algorand | polkadot | litecoin
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    address_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    address_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "chain", "address_fingerprint", name="uq_wallet_user_chain_fp"),)

    user: Mapped["User"] = relationship(back_populates="wallet_addresses")

    def __init__(self, **kwargs):
        # Constructor'da `address=` kabul edip otomatik şifrele.
        # SQLAlchemy default __init__ raw kolonları doldurur; biz `address`'i
        # önce setter'a düşürmek için manuel override ediyoruz.
        plaintext = kwargs.pop("address", None)
        super().__init__(**kwargs)
        if plaintext is not None:
            self.address = plaintext

    @hybrid_property
    def address(self) -> str:
        """Decrypt edilmiş plaintext address. ORM erişiminde her seferinde decrypt."""
        return decrypt_secret(self.address_encrypted)

    @address.setter  # type: ignore[no-redef]
    def address(self, value: str) -> None:
        """Plaintext set ederken Fernet şifrele + fingerprint hesapla."""
        self.address_encrypted = encrypt_secret(value)
        self.address_fingerprint = address_fingerprint(value)
