"""Kredi kartı şemaları (tanım + dönem içi borç + ekstre + taksit)."""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.services.currency import CurrencyType


class CreditCardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, max_length=60)
    last_4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    statement_day: int = Field(default=1, ge=1, le=28)
    payment_due_day: int = Field(default=10, ge=1, le=28)
    current_period_debt: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("999999999999.99"))
    notes: Optional[str] = Field(default=None, max_length=500)
    # Çoklu para birimi (v0.3.0) — None → "TRY".
    currency: Optional[CurrencyType] = None

    @field_validator("last_4")
    @classmethod
    def _digits_only(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not v.isdigit():
            raise ValueError("last_4 sadece rakam içerebilir")
        return v


class CreditCardUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, max_length=60)
    last_4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    statement_day: Optional[int] = Field(default=None, ge=1, le=28)
    payment_due_day: Optional[int] = Field(default=None, ge=1, le=28)
    current_period_debt: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    notes: Optional[str] = Field(default=None, max_length=500)
    currency: Optional[CurrencyType] = None


class CreditCardOut(BaseModel):
    id: int
    name: str
    bank_name: Optional[str] = None
    last_4: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    statement_day: int
    payment_due_day: int
    # Kullanıcı manuel girdiği "henüz ekstreye düşmemiş" tutar
    current_period_debt: Decimal
    notes: Optional[str] = None
    currency: str = "TRY"
    created_at: datetime
    updated_at: datetime

    # Hesaplanmış (server-side, read-only) — tutarlar kart para biriminde (orijinal)
    unpaid_statement_total: Decimal = Decimal(0)  # ödenmemiş ekstrelerin toplamı
    unpaid_statement_count: int = 0  # kaç adet ödenmemiş ekstre (>= 2 ise UI uyarı)
    future_installment_total: Decimal = Decimal(0)  # gelecek taksitlerin remaining × monthly toplamı
    period_debt: Decimal = Decimal(0)  # = unpaid_statement_total + current_period_debt
    total_debt: Decimal = Decimal(0)  # = period_debt + future_installment_total
    # TL karşılığı (güncel kurla — kart para birimi != TRY ise dolu)
    total_debt_tl: Decimal = Decimal(0)
    period_debt_tl: Decimal = Decimal(0)
    # Görüntüleme para birimi karşılıkları (Faz B — borç/ekstre cari/tahmin
    # niteliğinde olduğu için GÜNCEL kurla çevrilir). display==TRY → *_display == *_tl.
    display_currency: str = "TRY"
    period_debt_display: Decimal = Decimal(0)
    total_debt_display: Decimal = Decimal(0)

    model_config = {"from_attributes": True}


class CreditCardSummaryOut(BaseModel):
    """Tüm kartların özet bilgisi (dashboard kartı için)."""

    cards: list[CreditCardOut]
    # NOT: kartlar farklı para birimlerinde olabilir; toplamlar TL bazlıdır
    # (her kart güncel kurla TL'ye çevrilip toplanır).
    total_period_debt: Decimal  # tüm kartların dönem içi borç toplamı (TL)
    total_debt: Decimal  # tüm kartların toplam borcu (TL)
    # Geriye uyumluluk için eski isim — frontend yeni alanları kullanmalı
    total_current_period_debt: Decimal = Decimal(0)
    # Görüntüleme para birimi toplamları (Faz B — güncel kur).
    display_currency: str = "TRY"
    total_period_debt_display: Decimal = Decimal(0)
    total_debt_display: Decimal = Decimal(0)


# ---------------------------------------------------------------------------
# Aylık ekstreler
# ---------------------------------------------------------------------------
class StatementCreate(BaseModel):
    period_year: int = Field(..., ge=2020, le=2100)
    period_month: int = Field(..., ge=1, le=12)
    statement_amount: Decimal = Field(..., ge=0, le=Decimal("999999999999.99"))
    statement_date: date_type
    due_date: date_type
    paid_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class StatementUpdate(BaseModel):
    statement_amount: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    statement_date: Optional[date_type] = None
    due_date: Optional[date_type] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class StatementOut(BaseModel):
    id: int
    card_id: int
    period_year: int
    period_month: int
    statement_amount: Decimal
    statement_date: date_type
    due_date: date_type
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    currency: str = "TRY"
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Gelecek taksitler
# ---------------------------------------------------------------------------
class InstallmentCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=200)
    # Aylık taksit tutarı; toplam = monthly × installments_total (backend hesabı)
    monthly_amount: Decimal = Field(..., gt=0, le=Decimal("999999999999.99"))
    installments_total: int = Field(..., ge=1, le=120)
    first_due_date: date_type
    notes: Optional[str] = Field(default=None, max_length=500)
    # Ekstre import'ta o ekstrede görünen taksit sırası (X/Y'deki X). Manuel
    # girişte None — yalnız import yolu kullanır: gelecek taksit = total - paid.
    installments_paid: Optional[int] = Field(default=None, ge=1, le=120)


class InstallmentUpdate(BaseModel):
    description: Optional[str] = Field(default=None, min_length=1, max_length=200)
    monthly_amount: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("999999999999.99"))
    installments_total: Optional[int] = Field(default=None, ge=1, le=120)
    first_due_date: Optional[date_type] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class InstallmentOut(BaseModel):
    id: int
    card_id: int
    description: str
    total_amount: Decimal
    monthly_amount: Decimal
    installments_total: int
    installments_remaining: int
    first_due_date: date_type
    notes: Optional[str] = None
    currency: str = "TRY"
    created_at: datetime

    model_config = {"from_attributes": True}


class CardDetailOut(BaseModel):
    """Bir kartın tüm detayı: kart bilgisi + ekstreler + taksitler."""

    card: CreditCardOut
    statements: list[StatementOut]
    installments: list[InstallmentOut]


class PendingStatementCard(BaseModel):
    """Hesap kesim tarihi geçmiş ama o dönemin ekstresi yüklenmemiş kart.

    Girişte ekstre yükleme hatırlatma popup'ı için."""

    card_id: int
    name: str
    bank_name: Optional[str] = None
    last_4: Optional[str] = None
    period_year: int
    period_month: int
    cutoff_date: date_type  # bu dönemin hesap kesim tarihi (statement_day)


class DuePaymentItem(BaseModel):
    """Son ödeme tarihi yaklaşan/geçmiş ama henüz ödenmemiş ekstre.

    days_until_due < 0 → gecikmiş; 0 → bugün; >0 → yaklaşıyor."""

    card_id: int
    card_name: str
    bank_name: Optional[str] = None
    statement_id: int
    period_year: int
    period_month: int
    due_date: date_type
    statement_amount: Decimal
    days_until_due: int


class CreditCardRemindersResponse(BaseModel):
    """Girişte gösterilen kredi kartı hatırlatmaları (ekstre yükleme + ödeme)."""

    pending_statements: list[PendingStatementCard] = Field(default_factory=list)
    due_payments: list[DuePaymentItem] = Field(default_factory=list)
