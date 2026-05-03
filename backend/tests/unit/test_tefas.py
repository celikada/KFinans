"""
TEFAS servisi unit testleri — httpx çağrısı respx ile mock'lanır, DB gerekmez.
"""
import pytest
import respx
from decimal import Decimal
from httpx import Response
from app.services.tefas import TefasService, _EXPORT_URL


def _make_row(kod: str, portfoy: float, pay: float) -> dict:
    return {"fonKodu": kod, "sonPortfoyDegeri": portfoy, "sonPayAdedi": pay}


SAMPLE_ROWS = [
    _make_row("YAC", 100_000_000.0, 80_000_000.0),  # price = 1.250000
    _make_row("TTE", 500_000_000.0, 200_000_000.0),  # price = 2.500000
    _make_row("GO3", 300_000_000.0, 100_000_000.0),  # price = 3.000000
]


@pytest.mark.asyncio
async def test_fetch_prices_returns_correct_values():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=SAMPLE_ROWS))
        svc = TefasService([
            {"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi Fon"},
            {"code": "GO3", "quantity": 50.0, "name": "One Portföy Üçüncü Fon"},
        ])
        assets = await svc.fetch()

    assert len(assets) == 2
    yac = next(a for a in assets if a.symbol == "YAC")
    go3 = next(a for a in assets if a.symbol == "GO3")

    assert yac.unit_price_tl == Decimal("1.25")
    assert yac.liquid_quantity == Decimal("100.0")
    assert go3.unit_price_tl == Decimal("3.0")
    assert go3.liquid_quantity == Decimal("50.0")


@pytest.mark.asyncio
async def test_fetch_calculates_total_value():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=SAMPLE_ROWS))
        svc = TefasService([{"code": "TTE", "quantity": 200.0, "name": "Türkiye Teknoloji Fon"}])
        assets = await svc.fetch()

    tte = assets[0]
    total = tte.unit_price_tl * tte.liquid_quantity
    assert total == Decimal("2.5") * Decimal("200.0")


@pytest.mark.asyncio
async def test_fetch_raises_for_unknown_fund():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=SAMPLE_ROWS))
        svc = TefasService([{"code": "XXX", "quantity": 10.0, "name": "Bilinmeyen Fon"}])
        with pytest.raises(ValueError, match="TEFAS'ta fon bulunamadı: XXX"):
            await svc.fetch()


@pytest.mark.asyncio
async def test_fetch_code_is_case_insensitive():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=SAMPLE_ROWS))
        svc = TefasService([{"code": "yac", "quantity": 10.0, "name": "Yapı Kredi Fon"}])
        assets = await svc.fetch()

    assert assets[0].symbol == "YAC"


@pytest.mark.asyncio
async def test_fetch_skips_rows_with_zero_pay():
    rows_with_zero = SAMPLE_ROWS + [{"fonKodu": "BAD", "sonPortfoyDegeri": 1000.0, "sonPayAdedi": 0}]
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=rows_with_zero))
        svc = TefasService([{"code": "YAC", "quantity": 10.0, "name": "Test"}])
        assets = await svc.fetch()

    assert all(a.symbol != "BAD" for a in assets)


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(503))
        svc = TefasService([{"code": "YAC", "quantity": 10.0, "name": "Test"}])
        with pytest.raises(Exception):
            await svc.fetch()
