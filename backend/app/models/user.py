import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

_CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # conservative | balanced | aggressive
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verify_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    verify_token_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # SEC-001 (FAZ H): Password reset akisi — secrets.token_urlsafe(32), 1 saat TTL.
    # verify_token pattern'i kopyalanir (idempotent token rotation, generic response).
    reset_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # COMP-006 (FAZ H): KVKK m.5/1 ispat yuku — register'da rizalar timestamp'lenir,
    # revoke edilince NULL. terms / kvkk versiyonlanabilir (ileride re-accept).
    overseas_consent_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    kvkk_read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # AI-005 (FAZ H): Anthropic API'ye veri aktarimi icin ozel acik riza
    # (KVKK m.9). overseas_consent_at genel; bu kolon spesifik Anthropic.
    # version metin guncellendiginde re-accept zorunlu kilmak icin.
    anthropic_consent_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    anthropic_consent_version: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # COMP-029 (FAZ H): E-posta degistirme token rotation — yeni email hedefi
    # bekler, token tiklanip swap ettirilince eski email NULL'lanir.
    email_change_new: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_change_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    email_change_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # SEC-002 (FAZ H): Account lockout (OWASP ASVS V2.2.1)
    # Basarili login sonrasi 0'a sifirlanir; basarisiz login arttirir; 10 ust ustte
    # `locked_until = now + 15 dk` set edilir, hesap o sureyi gecene kadar login alamaz.
    # Per-IP rate limit (slowapi) saldirgan IP rotasyonu yaparsa atlatilabilir;
    # per-account counter aynı email'e farklı IP'lerden gelen brute-force'i durdurur.
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # MFA — TOTP (RFC 6238, audit #5 MFA).
    # `totp_secret` Fernet ciphertext (encrypt_secret/decrypt_secret); plaintext base32 ~32 char,
    # Fernet ciphertext ~100+ char — Text alani uygundur (VARCHAR(32) yetersiz olurdu).
    # `totp_enabled` setup tamamlanmadan True yapilmaz; setup yapilip enable cagrilana
    # kadar `totp_secret` dolu olabilir ama `totp_enabled=False` (yarim setup state).
    # `totp_recovery_codes` JSON list[str] olarak bcrypt-hashed 10 kod tutar — kayip
    # telefon recovery; her kod tek kullanimlik, kullanildigi anda listeden cikarilir.
    totp_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    totp_recovery_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Sürüm bildirimleri (release notes) — opt-in mail.
    # `is_admin`: sistemde rol yok; sadece bu flag yetkili kullaniciyi belirler
    # (release notes gonderme endpoint'i icin). Server default False — kimse
    # otomatik admin olmaz, DB'de elle set edilir.
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # KVKK acik riza: kayitta varsayilan KAPALI (onceden isaretli OLAMAZ).
    # Sadece email_verified=True VE bu True olan kullanicilara mail gider.
    release_notes_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Ödeme hatırlatması e-postası (push'a alternatif, opt-in). Her gün ödemesi
    # yaklaşan kredi kartı borçları için, email_verified=True olan opt-in
    # kullanıcılara Resend ile e-posta gönderilir. Kayıtta varsayılan KAPALI.
    payment_reminder_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Kalici user-ozel unsubscribe token (secrets.token_urlsafe). Mail icindeki
    # auth'suz unsubscribe linki bu token ile eslesir. Unique index.
    unsubscribe_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goal_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    goal_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    # Çoklu para birimi (v0.3.0): yeni gelir/gider/planlı kayıt formlarında
    # varsayılan para birimi tercihi. Kayıtta override edilebilir.
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    integrations: Mapped[list["Integration"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    wallet_addresses: Mapped[list["WalletAddress"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    investment_advice: Mapped[list["InvestmentAdvice"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    tefas_holdings: Mapped[list["TefasHolding"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    stock_holdings: Mapped[list["StockHolding"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    bes_holdings: Mapped[list["BesHolding"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    expenses: Mapped[list["Expense"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    planned_expenses: Mapped[list["PlannedExpense"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    incomes: Mapped[list["Income"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    recurring_incomes: Mapped[list["RecurringIncome"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    budgets: Mapped[list["Budget"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    commodity_holdings: Mapped[list["CommodityHolding"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    cash_holdings: Mapped[list["CashHolding"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    credit_cards: Mapped[list["CreditCard"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    manual_crypto_holdings: Mapped[list["ManualCryptoHolding"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", cascade=_CASCADE_ALL_DELETE_ORPHAN)
