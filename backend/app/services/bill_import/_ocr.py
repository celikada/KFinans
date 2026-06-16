"""Taranmış görüntü-PDF faturalar için OCR fallback (Osmangazi/Zorlu Elektrik gibi).

Metin katmanı olmayan PDF'lerde `extract_text` boş döner; bu modül pypdfium2 ile
sayfayı görüntüye render edip (poppler gerektirmez) pytesseract (tesseract-ocr +
Türkçe dil paketi, Dockerfile'da apt ile kurulu) ile metni çıkarır. OCR gürültülü
olabilir → çıkan metin yine deterministik parser'a gider, kullanıcı önizlemede
tutar/tarihleri onaylar/düzeltir (asla otomatik kayıt yok).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# İlk N sayfa OCR'lanır (fatura genelde 1. sayfada); fazlası gereksiz CPU.
_MAX_PAGES = 2
# Render çözünürlüğü — 300 DPI tesseract için iyi denge (daha yüksek = yavaş).
_DPI = 300


def ocr_pdf(pdf_bytes: bytes) -> str:
    """Görüntü-PDF'in ilk sayfalarını OCR ile metne çevirir (Türkçe).

    Bağımlılık (pypdfium2/pytesseract) veya tesseract binary yoksa boş string
    döner (endpoint "okunamadı, elle girin" 422 verir — fail-safe).
    """
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as e:  # pragma: no cover - bağımlılık eksikliği
        logger.warning("OCR bağımlılığı yok (%s) — görüntü-PDF okunamaz", e)
        return ""

    parts: list[str] = []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
    except Exception as e:  # pragma: no cover - bozuk PDF
        logger.warning("OCR: PDF açılamadı: %s", e)
        return ""
    try:
        for i in range(min(len(pdf), _MAX_PAGES)):
            image = pdf[i].render(scale=_DPI / 72).to_pil()
            parts.append(pytesseract.image_to_string(image, lang="tur"))
    except Exception as e:  # pragma: no cover - tesseract/render hatası
        logger.warning("OCR render/tesseract hatası: %s", e)
        return ""
    finally:
        pdf.close()
    return "\n".join(parts)
