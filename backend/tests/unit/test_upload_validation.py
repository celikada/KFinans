"""SEC-009 (FAZ H): upload_validation.py unit testleri.

Magic-byte + boyut + extension dogrulamasi:
- gecerli .xlsx (PK\\x03\\x04) -> bytes doner
- gecerli .xls (OLE2/CFB header) -> bytes doner
- yanlis magic byte -> 422
- extension mismatch -> 422
- bos dosya -> 422
- max size asildi -> 413
"""
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.core.upload_validation import (
    _XLS_MAGIC,
    _XLSX_MAGIC,
    validate_excel_upload,
)


def _make_upload(filename: str, content: bytes) -> UploadFile:
    """Test helper: minimal UploadFile mock."""
    return UploadFile(filename=filename, file=BytesIO(content))


# ─── Happy path ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_xlsx_returns_content():
    """PK\\x03\\x04 ile baslayan .xlsx kabul edilir."""
    content = _XLSX_MAGIC + b"\x00" * 100  # mini ZIP header + padding
    file = _make_upload("test.xlsx", content)
    result = await validate_excel_upload(file)
    assert result == content


@pytest.mark.asyncio
async def test_valid_xls_returns_content():
    """OLE2 magic ile baslayan .xls kabul edilir."""
    content = _XLS_MAGIC + b"\x00" * 100
    file = _make_upload("test.xls", content)
    result = await validate_excel_upload(file)
    assert result == content


@pytest.mark.asyncio
async def test_case_insensitive_extension():
    """.XLSX da kabul edilir (case-insensitive)."""
    content = _XLSX_MAGIC + b"\x00" * 100
    file = _make_upload("REPORT.XLSX", content)
    result = await validate_excel_upload(file)
    assert result == content


# ─── Rejection: extension ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_filename_rejected():
    """Filename eksik -> 422."""
    file = _make_upload("", b"PK\x03\x04")
    with pytest.raises(HTTPException) as exc:
        await validate_excel_upload(file)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_wrong_extension_rejected():
    """.pdf, .exe, vs. -> 422."""
    file = _make_upload("malware.exe", _XLSX_MAGIC + b"\x00" * 50)
    with pytest.raises(HTTPException) as exc:
        await validate_excel_upload(file)
    assert exc.value.status_code == 422


# ─── Rejection: magic byte ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_polyglot_pdf_disguised_as_xlsx_rejected():
    """PDF magic byte ama filename .xlsx -> 422 (polyglot saldirisi)."""
    content = b"%PDF-1.4\n" + b"\x00" * 100  # PDF header
    file = _make_upload("evil.xlsx", content)
    with pytest.raises(HTTPException) as exc:
        await validate_excel_upload(file)
    assert exc.value.status_code == 422
    assert "Geçersiz dosya formatı" in exc.value.detail


@pytest.mark.asyncio
async def test_xlsx_magic_in_xls_file_rejected():
    """.xls extension ama icerik ZIP (XLSX) -> 422."""
    file = _make_upload("fake.xls", _XLSX_MAGIC + b"\x00" * 50)
    with pytest.raises(HTTPException) as exc:
        await validate_excel_upload(file)
    assert exc.value.status_code == 422


# ─── Rejection: size ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oversize_rejected():
    """max_size_mb=1 limiti asildiginda 413."""
    big = _XLSX_MAGIC + b"\x00" * (2 * 1024 * 1024)  # 2 MB
    file = _make_upload("huge.xlsx", big)
    with pytest.raises(HTTPException) as exc:
        await validate_excel_upload(file, max_size_mb=1)
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_empty_file_rejected():
    """Bos dosya -> 422 (magic check'ten once)."""
    file = _make_upload("empty.xlsx", b"")
    with pytest.raises(HTTPException) as exc:
        await validate_excel_upload(file)
    assert exc.value.status_code == 422
    assert "boş" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_settings_default_used_when_max_size_none():
    """max_size_mb None -> settings.max_upload_size_mb kullanir."""
    # Default 5 MB; 100 byte dosya rahatlikla altinda
    file = _make_upload("ok.xlsx", _XLSX_MAGIC + b"\x00" * 50)
    assert settings.max_upload_size_mb >= 1
    result = await validate_excel_upload(file)  # max_size_mb belirtilmedi
    assert len(result) == 54
