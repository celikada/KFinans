"""SEC-009 (FAZ H): File upload validation — magic-byte + boyut limiti.

10 import endpoint'i (BES, expense, income, commodity, manual_crypto,
wallets, stocks MKK + manuel, tefas MKK + manuel) bu helper'i kullanir.

Onceki davranis: sadece `file.filename.endswith((".xlsx", ".xls"))` —
attacker filename'i `.xlsx` yapıp icine sahte payload koyabilir
(polyglot file). Magic-byte kontrolu gercek formati dogrular.

Boyut limiti: `settings.max_upload_size_mb` (default 5MB). DoS koruma
(100MB Excel openpyxl memory blow olmasin).
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, UploadFile, status

from app.config import settings

logger = logging.getLogger(__name__)

# XLSX = ZIP container (PK\x03\x04 local file header signature).
_XLSX_MAGIC = b"PK\x03\x04"
# XLS = OLE2/CFB compound file header.
_XLS_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


async def validate_excel_upload(
    file: UploadFile,
    *,
    max_size_mb: int | None = None,
) -> bytes:
    """UploadFile'i 3 katmanda dogrula ve content bytes dondur.

    1. Filename extension `.xlsx` veya `.xls` (case-insensitive).
    2. Boyut limiti `max_size_mb` (default settings.max_upload_size_mb).
    3. Magic byte (ilk byte'lar header eslemeli).

    Hatalar:
    - 422 Unprocessable Entity: extension veya magic byte yanlis.
    - 413 Payload Too Large: max size asildi.

    Returns: content bytes (downstream `openpyxl.load_workbook(BytesIO(...))`).
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosya adı eksik.",
        )

    fname_lower = file.filename.lower()
    if not fname_lower.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lütfen .xlsx veya .xls dosyası yükleyin.",
        )

    max_mb = max_size_mb if max_size_mb is not None else settings.max_upload_size_mb
    max_bytes = max_mb * 1024 * 1024

    content = await file.read()

    if len(content) > max_bytes:
        logger.warning(
            "Upload too large: filename=%s size=%d max=%d",
            file.filename, len(content), max_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya çok büyük (en fazla {max_mb} MB).",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosya boş.",
        )

    # Magic byte: filename extension dogrulamasi ile uyumlu mu?
    is_xlsx = fname_lower.endswith(".xlsx")
    expected = _XLSX_MAGIC if is_xlsx else _XLS_MAGIC

    if not content.startswith(expected):
        logger.warning(
            "Upload magic byte mismatch: filename=%s expected=%s actual=%s",
            file.filename,
            expected.hex(),
            content[: len(expected)].hex() if len(content) >= len(expected) else "<short>",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geçersiz dosya formatı. Lütfen gerçek bir Excel dosyası yükleyin.",
        )

    return content
