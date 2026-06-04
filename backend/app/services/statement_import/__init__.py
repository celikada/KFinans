"""Kredi karti ekstresi (PDF) import — parser registry + PDF metin cikarma.

Yeni bir banka eklemek: o banka icin `StatementParser` uyumlu bir sinif yaz
(ornek: `ziraat.py`) ve `PARSERS` listesine ekle. Format tanima `matches()` ile,
veri ayiklama `parse()` ile yapilir.

Fail-safe ilkesi: hicbir parser eslesmezse `detect_parser` None doner (endpoint
"banka taninmadi" uyarisi verir). Parser eslesir ama beklenen alanlar bulunamazsa
`parse()` `ValueError` firlatir (endpoint "format degismis olabilir" uyarisi verir).
Hicbir durumda tahmini/yanlis veri kaydedilmez.
"""

from __future__ import annotations

import io

import pdfplumber

from .akbank import AkbankParser
from .base import ParsedInstallment, ParsedStatement, StatementParser
from .enpara import EnparaParser
from .vakifbank import VakifBankParser
from .ziraat import ZiraatParser

# Desteklenen banka parser'lari. Yeni banka buraya eklenir (siralama onemli:
# ilk `matches()` true olan secilir; banka adi anahtar kelimeleri ortusmemeli).
PARSERS: list[StatementParser] = [
    ZiraatParser(),
    EnparaParser(),
    VakifBankParser(),
    AkbankParser(),
]


def extract_text(pdf_bytes: bytes) -> str:
    """PDF byte'larindan tum sayfalarin metnini birlestirip dondur."""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def detect_parser(text: str) -> StatementParser | None:
    """Metne uygun ilk parser'i dondur; hicbiri eslesmezse None."""
    for parser in PARSERS:
        if parser.matches(text):
            return parser
    return None


__all__ = [
    "PARSERS",
    "ParsedInstallment",
    "ParsedStatement",
    "StatementParser",
    "detect_parser",
    "extract_text",
]
