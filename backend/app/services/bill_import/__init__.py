"""Abonelik faturası (PDF) import — parser registry + PDF metin çıkarma.

Yeni kurum eklemek: o kurum için `BillParser` uyumlu bir sınıf yaz ve `PARSERS`
listesine ekle. Format tanıma `matches()`, veri ayıklama `parse()` ile.

Fail-safe: hiçbir parser eşleşmezse `detect_parser` None döner (endpoint "kurum
tanınmadı" 422). Parser eşleşir ama alanlar bulunamazsa `parse()` `ValueError`
fırlatır (endpoint "format değişmiş" 422). Metin katmanı yoksa (taranmış görüntü)
endpoint "metin yok, elle girin" 422 verir. Hiçbir durumda tahmini veri yazılmaz.
"""

from __future__ import annotations

import io

import pdfplumber

from ._ocr import ocr_pdf
from .base import BillParser, ParsedBill
from .esgaz import EsgazParser
from .osmangazi import OsmangaziParser
from .ttnet import TtnetParser
from .vodafone import VodafoneParser

# Desteklenen kurum parser'ları. Sıralama: ilk `matches()` true olan seçilir
# (imzalar örtüşmemeli — esgaz/vodafone/ttnet/osmangazi ayrık anahtar kelimeler).
# Osmangazi metni genelde OCR'dan gelir (görüntü-PDF); diğerleri saf metin.
PARSERS: list[BillParser] = [
    EsgazParser(),
    VodafoneParser(),
    TtnetParser(),
    OsmangaziParser(),
]


def extract_text(pdf_bytes: bytes) -> str:
    """PDF byte'larından tüm sayfaların metnini birleştirip döndür."""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def detect_parser(text: str) -> BillParser | None:
    """Metne uygun ilk parser'ı döndür; hiçbiri eşleşmezse None."""
    for parser in PARSERS:
        if parser.matches(text):
            return parser
    return None


__all__ = [
    "PARSERS",
    "BillParser",
    "ParsedBill",
    "detect_parser",
    "extract_text",
    "ocr_pdf",
]
