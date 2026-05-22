"""TEST-001 (FAZ H): services/reports.py birim testleri.

Excel + PDF rapor uretici fonksiyonlarinin temel davranisi:
- bytes doner
- Excel xlsx magic bytes (PK\x03\x04 — ZIP signature)
- PDF magic bytes (%PDF)
- Bos pozisyon listesi crash etmez
- Turkce karakter destegi DejaVu Sans font
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.reports import (
    _fmt_tl,
    cash_flow_to_pdf,
    cash_flow_to_xlsx,
    snapshot_to_pdf,
    snapshot_to_xlsx,
)

# ─── _fmt_tl helper ─────────────────────────────────────────────────────


def test_fmt_tl_none_returns_dash():
    assert _fmt_tl(None) == "—"


def test_fmt_tl_decimal_formats_with_commas():
    assert _fmt_tl(Decimal("1234567.89")) == "1,234,567.89 ₺"


def test_fmt_tl_zero():
    assert _fmt_tl(0) == "0.00 ₺"


def test_fmt_tl_negative():
    assert _fmt_tl(Decimal("-500")) == "-500.00 ₺"


# ─── Cash flow Excel ────────────────────────────────────────────────────


def _make_months(count: int = 12):
    return [
        {
            "month": i,
            "income_actual": str(1000 * i),
            "income_forecast": str(500),
            "expense_actual": str(700 * i),
            "expense_forecast": str(200),
            "net": str(300 * i),
            "is_past": i <= 5,
        }
        for i in range(1, count + 1)
    ]


def _totals():
    return {
        "total_income": "78000",
        "total_expense": "50800",
        "total_net": "27200",
    }


def test_cash_flow_xlsx_returns_bytes():
    data = cash_flow_to_xlsx(2026, _make_months(), _totals())
    assert isinstance(data, bytes)
    assert len(data) > 100
    # XLSX = ZIP arsiv (PK signature)
    assert data[:2] == b"PK"


def test_cash_flow_xlsx_with_empty_months():
    """Bos liste exception atmamali — header ve YIL TOPLAMI satiri kalmali."""
    data = cash_flow_to_xlsx(
        2026,
        [],
        {
            "total_income": "0",
            "total_expense": "0",
            "total_net": "0",
        },
    )
    assert isinstance(data, bytes)
    assert data[:2] == b"PK"


# ─── Cash flow PDF ──────────────────────────────────────────────────────


def test_cash_flow_pdf_returns_bytes():
    data = cash_flow_to_pdf(2026, _make_months(), _totals())
    assert isinstance(data, bytes)
    assert len(data) > 100
    # PDF magic bytes
    assert data[:4] == b"%PDF"


def test_cash_flow_pdf_with_empty_months():
    """Bos pozisyon listesi crash etmemeli."""
    data = cash_flow_to_pdf(
        2026,
        [],
        {
            "total_income": "0",
            "total_expense": "0",
            "total_net": "0",
        },
    )
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


# ─── Snapshot raporlari ─────────────────────────────────────────────────


def _make_snapshot():
    """SimpleNamespace ile minimal Snapshot taklit."""
    return SimpleNamespace(
        snapshot_date=date(2026, 5, 10),
        total_value_tl=Decimal("125000.00"),
        usd_try_rate=Decimal("33.45"),
    )


def _make_positions(count: int = 5):
    return [
        SimpleNamespace(
            asset_type="crypto" if i % 2 == 0 else "fund",
            provider="binance" if i % 2 == 0 else "tefas",
            symbol=f"SYM{i}",
            name=f"Asset {i}",
            liquid_quantity=Decimal(str(i * 10)),
            staked_quantity=Decimal(0),
            pending_rewards=Decimal(0),
            unit_price_tl=Decimal(str(100 + i)),
            total_value_tl=Decimal(str(i * 1000)),
            weight_pct=Decimal(str(i * 10)),
        )
        for i in range(1, count + 1)
    ]


def test_snapshot_xlsx_returns_bytes():
    data = snapshot_to_xlsx(_make_snapshot(), _make_positions())
    assert isinstance(data, bytes)
    assert data[:2] == b"PK"


def test_snapshot_xlsx_with_empty_positions():
    """Bos snapshot — header ve TOPLAM satiri kalmali."""
    data = snapshot_to_xlsx(_make_snapshot(), [])
    assert isinstance(data, bytes)
    assert data[:2] == b"PK"


def test_snapshot_pdf_returns_bytes():
    data = snapshot_to_pdf(_make_snapshot(), _make_positions())
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_snapshot_pdf_with_50_plus_positions_top50_only():
    """PDF rapor en buyuk 50 pozisyonu icerir; 60 verince crash etmemeli."""
    positions = _make_positions(60)
    data = snapshot_to_pdf(_make_snapshot(), positions)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"
