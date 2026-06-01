"""Regression guard: Content-Disposition header'ları latin-1 (ASCII-safe) olmalı.

Bug (2026-06-01): wallets export endpoint'i `Content-Disposition: filename=
blockchain-cüzdanları.xlsx` döndürüyordu. 'ı' (U+0131) latin-1 ile encode
edilemez; ASGI/Starlette HTTP header'ları latin-1 ile serialize ettiği için
UnicodeEncodeError → 500. Düzeltme: ASCII dosya adı (blockchain-cuzdanlari.xlsx).

Bu test, app kaynağındaki TÜM `Content-Disposition` satırlarının latin-1
encode edilebilir olduğunu doğrular — aynı sınıf hatanın tekrarını engeller.
Yeni bir export endpoint'i Türkçe karakterli dosya adı eklerse burada yakalanır;
Türkçe gerekiyorsa RFC 5987 `filename*=UTF-8''...` kullanılmalı (ayrıca ASCII
fallback `filename=` bırakılarak).
"""

from __future__ import annotations

import pathlib

_APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"


def test_all_content_disposition_headers_are_latin1_encodable() -> None:
    offenders: list[str] = []
    for py_file in _APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
            if "Content-Disposition" not in line:
                continue
            try:
                line.encode("latin-1")
            except UnicodeEncodeError:
                rel = py_file.relative_to(_APP_DIR.parent)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Content-Disposition satırı latin-1 ile encode edilemiyor (ASGI 500 riski). "
        "Dosya adını ASCII yap veya RFC 5987 filename*=UTF-8'' kullan:\n  " + "\n  ".join(offenders)
    )
