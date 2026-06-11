"""Kredi karti ekstresi (PDF) import şemaları: preview çıktısı + commit girdisi.

preview endpoint'i `ParsedStatementOut` döner (DB'ye yazmaz); kullanıcı önizleyip
düzeltir; commit endpoint'i `StatementImportCommitIn` alıp kalıcılaştırır.
"""

from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.credit_card import InstallmentCreate, StatementCreate
from app.services.currency import CurrencyType


class ParsedInstallmentOut(BaseModel):
    """Parser'ın ekstreden ayıkladığı bir taksit (önizleme, salt okunur)."""

    description: str
    total_amount: Decimal
    monthly_amount: Decimal
    installments_total: int
    installments_paid: int
    first_due_date: date_type


class ParsedStatementOut(BaseModel):
    """preview endpoint çıktısı: ayıklanmış ekstre + kart eşleşmesi + uyarılar."""

    bank_name: str
    last_4: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    statement_day: int
    payment_due_day: int
    period_year: int
    period_month: int
    statement_amount: Decimal
    statement_date: date_type
    due_date: date_type
    installments: list[ParsedInstallmentOut] = Field(default_factory=list)
    # Mevcut kartla eşleşme (user_id + last_4 + bank_name) — None ise yeni kart.
    matched_card_id: Optional[int] = None
    # Parse belirsizlikleri (kullanıcı kaydetmeden kontrol etsin).
    warnings: list[str] = Field(default_factory=list)


class StatementImportCommitIn(BaseModel):
    """commit endpoint girdisi: kullanıcının onayladığı/düzelttiği veri.

    `target_card_id` doluysa o karta eklenir (IDOR kontrolü endpoint'te);
    None ise yeni kart oluşturulur (çoklu kart tek hesapta toplanır).
    """

    target_card_id: Optional[int] = None
    # Kart bilgisi (yeni kart için zorunlu; mevcut kartta bank/limit güncellenir).
    name: str = Field(..., min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, max_length=60)
    last_4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    statement_day: int = Field(default=1, ge=1, le=28)
    payment_due_day: int = Field(default=10, ge=1, le=28)
    # Kart para birimi — ekstre + taksitlere de devredilir (None → "TRY").
    currency: Optional[CurrencyType] = None
    statement: StatementCreate
    installments: list[InstallmentCreate] = Field(default_factory=list)
