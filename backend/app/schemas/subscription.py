"""Abonelik (fatura/utility) şemaları + kurum kataloğu.

3 durumlu yaşam döngüsü: budget (implicit) → issued (fatura geldi) → paid (ödendi).
"""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.services.currency import CurrencyType

# --- Kurum kataloğu (genişletilebilir) -------------------------------------
# code -> (görünen ad, kategori). Kategori frontend ikon/renk + filtre için.
SubscriptionCategory = Literal["gas", "electricity", "internet", "phone"]
PaymentMethod = Literal["cash", "credit_card"]
BillStatus = Literal["budget", "issued", "paid"]

PROVIDERS: dict[str, tuple[str, str]] = {
    "esgaz": ("ESGAZ", "gas"),
    "zorlu_enerji": ("Zorlu Enerji", "electricity"),
    "osmangazi_elektrik": ("Osmangazi Elektrik", "electricity"),
    "ttnet": ("TTNET", "internet"),
    "vodafone": ("Vodafone", "phone"),
}


class ProviderOut(BaseModel):
    code: str
    name: str
    category: str


def provider_catalog() -> list[ProviderOut]:
    return [ProviderOut(code=code, name=name, category=cat) for code, (name, cat) in PROVIDERS.items()]


# --- Abonelik --------------------------------------------------------------
_AMOUNT_MAX = Decimal("999999999999.99")


class SubscriptionCreate(BaseModel):
    provider_code: str = Field(..., min_length=1, max_length=40)
    subscriber_no: str = Field(..., min_length=1, max_length=64)
    label: Optional[str] = Field(default=None, max_length=100)
    budget_amount: Decimal = Field(..., ge=0, le=_AMOUNT_MAX)
    currency: Optional[CurrencyType] = None
    billing_day: Optional[int] = Field(default=None, ge=1, le=28)
    due_day: Optional[int] = Field(default=None, ge=1, le=28)
    active: bool = True
    notes: Optional[str] = Field(default=None, max_length=500)


class SubscriptionUpdate(BaseModel):
    provider_code: Optional[str] = Field(default=None, min_length=1, max_length=40)
    subscriber_no: Optional[str] = Field(default=None, min_length=1, max_length=64)
    label: Optional[str] = Field(default=None, max_length=100)
    budget_amount: Optional[Decimal] = Field(default=None, ge=0, le=_AMOUNT_MAX)
    currency: Optional[CurrencyType] = None
    billing_day: Optional[int] = Field(default=None, ge=1, le=28)
    due_day: Optional[int] = Field(default=None, ge=1, le=28)
    active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class SubscriptionOut(BaseModel):
    id: int
    provider_code: str
    provider_name: str = ""  # katalogdan zenginleştirilir (router doldurur)
    category: str
    subscriber_no: str
    label: Optional[str] = None
    budget_amount: Decimal
    currency: str = "TRY"
    billing_day: Optional[int] = None
    due_day: Optional[int] = None
    active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Bu ay (içinde bulunulan dönem) için türetilmiş durum (router doldurur)
    current_status: BillStatus = "budget"
    current_amount: Decimal = Decimal(0)
    current_bill_id: Optional[int] = None

    model_config = {"from_attributes": True}


# --- Fatura dönemi ---------------------------------------------------------
class SubscriptionBillIssue(BaseModel):
    """budget → issued: fatura tutarı + tarihleri gir (period upsert)."""

    period_year: int = Field(..., ge=2000, le=2100)
    period_month: int = Field(..., ge=1, le=12)
    bill_amount: Decimal = Field(..., ge=0, le=_AMOUNT_MAX)
    bill_date: date_type
    due_date: date_type
    notes: Optional[str] = Field(default=None, max_length=500)


class SubscriptionBillPay(BaseModel):
    """issued → paid: ödeme şekli (çift sayım için credit_card_id'yi belirler)."""

    payment_method: PaymentMethod
    credit_card_id: Optional[int] = None
    paid_at: Optional[datetime] = None


class SubscriptionBillOut(BaseModel):
    id: int
    subscription_id: int
    period_year: int
    period_month: int
    currency: str = "TRY"
    bill_amount: Decimal
    bill_date: date_type
    due_date: date_type
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    credit_card_id: Optional[int] = None
    expense_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    status: BillStatus = "issued"  # router türetir (paid_at'e göre)

    model_config = {"from_attributes": True}


class SubscriptionPeriodOut(BaseModel):
    """Dönem listesi satırı — materialize edilmiş (issued/paid) veya sentezlenmiş (budget)."""

    period_year: int
    period_month: int
    status: BillStatus
    amount: Decimal  # budget → subscription.budget_amount; aksi → bill_amount
    currency: str = "TRY"
    bill_id: Optional[int] = None
    bill_date: Optional[date_type] = None
    due_date: Optional[date_type] = None
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None


class SubscriptionSummaryOut(BaseModel):
    display_currency: str = "TRY"
    # Bu ay tahmini (issued varsa bill_amount, yoksa budget) — display currency
    this_month_estimate: Decimal = Decimal(0)
    # Yıl sonuna kadar toplam beklenti (kalan aylar budget/issued) — display currency
    remaining_year_estimate: Decimal = Decimal(0)
    active_count: int = 0


# --- Hatırlatma ------------------------------------------------------------
class SubscriptionDuePayment(BaseModel):
    subscription_id: int
    bill_id: int
    provider_name: str
    label: Optional[str] = None
    bill_amount: Decimal
    currency: str = "TRY"
    due_date: date_type
    days_until_due: int


class SubscriptionPendingBill(BaseModel):
    subscription_id: int
    provider_name: str
    label: Optional[str] = None
    period_year: int
    period_month: int


class SubscriptionRemindersOut(BaseModel):
    due_payments: list[SubscriptionDuePayment] = []
    pending_bills: list[SubscriptionPendingBill] = []
