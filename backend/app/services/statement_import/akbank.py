"""Akbank Axess kredi kartı ekstresi parser'i (deterministik, glyph çözümlü).

Akbank/Axess PDF'lerinin metin katmanı custom font encoding kullanır; pdfplumber
glyph'leri `(cid:NNN)` token'ları + dağınık Latin karakterler olarak çıkarır
(font'ta ToUnicode CMap yok). Rakamlar ve finansal semboller deterministik çözülür:
- `(cid:240..249)` → 0..9 (CID = ASCII + 0xC0); ayrıca Latin glyph'ler `æ`=1 `ı`=5 `ł`=8 `ø`=9.
- `k`=binlik nokta, `K`=ondalık virgül, `\\`=maske `*`, `GGaAAaYYYY`=`GG/AA/YYYY`.

Harf glyph'leri context-dependent (güvenilmez) → ETIKETLER decode edilmez. Bunun
yerine cid'den bağımsız, format-bazlı işaretler kullanılır: maskeli kart numarası
ve "ekstre dönemi" tarih aralığı. Bu ikisi birlikte yalnız Akbank ekstresinde
bulunur (`matches`). Değerler konumdan çıkarılır (ilk tarih = son ödeme, dönem
aralığı sonu = hesap kesim, ilk tutar = dönem borcu, en büyük tutar = kart limiti).
Format değişirse alanlar bulunamaz → ValueError → fail-safe (kayıt yok, uyarı).
"""

from __future__ import annotations

import re

from ._utils import clamp_day, parse_amount, parse_date
from .base import ParsedStatement

# Latin glyph → rakam (cid dışı kalan rakam glyph'leri).
_LATIN_DIGIT = str.maketrans({"æ": "1", "ı": "5", "ł": "8", "ø": "9"})

# Maskeli kart no: "5218@07**@****@6072" → son grup. (cid-bağımsız format işareti)
_CARD_RE = re.compile(r"(\d{4})@\d{2}\*+@\*+@(\d{4})")
# Ekstre dönemi aralığı: "25/04/2026‘23/05/2026" → 2. tarih = hesap kesim.
_PERIOD_RE = re.compile(r"(\d{2}/\d{2}/\d{4})[‘'`´’](\d{2}/\d{2}/\d{4})")
_DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")
_AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


def _decode(text: str) -> str:
    """pdfplumber garbled metnini yarı-decode et: rakam + finansal sembol + tarih."""
    text = re.sub(
        r"\(cid:(\d+)\)",
        lambda m: chr(int(m.group(1)) - 192) if 240 <= int(m.group(1)) <= 249 else m.group(0),
        text,
    )
    text = text.translate(_LATIN_DIGIT)
    text = text.replace("k", ".").replace("K", ",").replace("\\", "*")
    text = re.sub(r"(\d{2})a(\d{2})a(\d{4})", r"\1/\2/\3", text)
    return text


class AkbankParser:
    """Akbank Axess ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "akbank"

    def matches(self, text: str) -> bool:
        d = _decode(text)
        # Maskeli kart + ekstre dönemi aralığı birlikte → Akbank/Axess.
        return bool(_CARD_RE.search(d)) and bool(_PERIOD_RE.search(d))

    def parse(self, text: str) -> ParsedStatement:
        return self._extract(_decode(text))

    def _extract(self, d: str) -> ParsedStatement:
        card = _CARD_RE.search(d)
        period = _PERIOD_RE.search(d)
        if not card or not period:
            raise ValueError("Akbank/Axess ekstresi okunamadı — format değişmiş olabilir.")

        last_4 = card.group(2)
        statement_date = parse_date(period.group(2))  # dönem aralığı sonu = hesap kesim

        due_match = _DATE_RE.search(d)  # ilk tarih = son ödeme (başlıkta önce gelir)
        if not due_match:
            raise ValueError("Son ödeme tarihi bulunamadı — ekstre formatı değişmiş olabilir.")
        due_date = parse_date(due_match.group(0))

        amt_match = _AMOUNT_RE.search(d)  # ilk tutar = dönem borcu
        if not amt_match:
            raise ValueError("Dönem borcu bulunamadı — ekstre formatı değişmiş olabilir.")
        statement_amount = parse_amount(amt_match.group(0))

        # Kart limiti = en büyük tutar (kullanılabilir/nakit avans limiti ≤ kart limiti).
        amounts = [parse_amount(a) for a in _AMOUNT_RE.findall(d)]
        credit_limit = max(amounts) if amounts else None

        return ParsedStatement(
            bank_name="Akbank",
            last_4=last_4,
            credit_limit=credit_limit,
            statement_day=clamp_day(statement_date.day),
            payment_due_day=clamp_day(due_date.day),
            period_year=statement_date.year,
            period_month=statement_date.month,
            statement_amount=statement_amount,
            statement_date=statement_date,
            due_date=due_date,
            installments=[],
            warnings=[
                "Akbank/Axess ekstresi şifreli metin katmanından çözüldü; tutar, tarih "
                "ve kart limitini (en büyük tutar olarak alınır) kaydetmeden önce kontrol edin."
            ],
        )
