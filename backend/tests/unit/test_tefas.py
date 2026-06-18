"""
TEFAS servisi unit testleri — httpx çağrısı respx ile mock'lanır, DB gerekmez.
"""

from decimal import Decimal

import httpx
import pytest
import respx
from httpx import Response

from app.services.tefas import _EXPORT_URL, TefasService, fetch_tefas_prices_by_codes, reset_tefas_cache


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
        svc = TefasService(
            [
                {"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi Fon"},
                {"code": "GO3", "quantity": 50.0, "name": "One Portföy Üçüncü Fon"},
            ]
        )
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
async def test_fetch_skip_missing_does_not_raise():
    """skip_missing=True: fiyatlanamayan fon (0 portföy değerli AFO benzeri) ATLANIR,
    raise ETMEZ — tek fiyatsız fon tüm TEFAS kartını çökertmesin (prod AFO bug'ı)."""
    reset_tefas_cache()
    # AFO: portföy/pay = 0 → grid'e girmez (pay>0 filtresi) → "fiyatlanamaz"
    rows = SAMPLE_ROWS + [{"fonKodu": "AFO", "sonPortfoyDegeri": 0, "sonPayAdedi": 0}]
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=rows))
        svc = TefasService(
            [
                {"code": "YAC", "quantity": 10.0, "name": "Yapı Kredi Fon"},
                {"code": "AFO", "quantity": 5.0, "name": "Ak Portföy Altın Fonu"},
            ]
        )
        assets = await svc.fetch(skip_missing=True)

    # YAC fiyatlandı, AFO atlandı (raise yok)
    assert [a.symbol for a in assets] == ["YAC"]
    assert svc.missing_codes == ["AFO"]


@pytest.mark.asyncio
async def test_fetch_default_still_raises_for_missing():
    """skip_missing=False (varsayılan, preview/validation): eksik fon → ValueError korunur."""
    reset_tefas_cache()
    rows = SAMPLE_ROWS + [{"fonKodu": "AFO", "sonPortfoyDegeri": 0, "sonPayAdedi": 0}]
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=rows))
        svc = TefasService([{"code": "AFO", "quantity": 5.0, "name": "Altın Fonu"}])
        with pytest.raises(ValueError, match="TEFAS'ta fon bulunamadı: AFO"):
            await svc.fetch()


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(503))
        svc = TefasService([{"code": "YAC", "quantity": 10.0, "name": "Test"}])
        with pytest.raises(httpx.HTTPStatusError):
            await svc.fetch()


# ─── fetch_tefas_prices_by_codes ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prices_by_codes_empty_returns_empty():
    assert await fetch_tefas_prices_by_codes([]) == {}


@pytest.mark.asyncio
async def test_prices_by_codes_returns_price_map():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=SAMPLE_ROWS))
        out = await fetch_tefas_prices_by_codes(["YAC", "TTE"])
    assert out["YAC"] == Decimal("1.25")
    assert out["TTE"] == Decimal("2.5")


@pytest.mark.asyncio
async def test_prices_by_codes_swallows_errors():
    """HTTP/fon-bulunamadi hatasinda bos dict — caller best-effort."""
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(503))
        out = await fetch_tefas_prices_by_codes(["YAC"])
    assert out == {}


@pytest.mark.asyncio
async def test_prices_by_codes_missing_code_excluded():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=SAMPLE_ROWS))
        out = await fetch_tefas_prices_by_codes(["YAC", "NOPE"])
    # NOPE bulunamayinca fetch() ValueError firlatir → tum dict bos doner
    assert out == {}


# ─── health_check ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_returns_true_on_200():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=[]))
        svc = TefasService([])
        assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_returns_false_on_error():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(500))
        svc = TefasService([])
        assert await svc.health_check() is False


@pytest.mark.asyncio
async def test_health_check_false_on_exception():
    with respx.mock:
        respx.post(_EXPORT_URL).mock(side_effect=httpx.ConnectError("boom"))
        svc = TefasService([])
        assert await svc.health_check() is False
