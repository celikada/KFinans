"""TEST-001: services/blockchain/litecoin.py xpub HD + scan + health birim testleri.

litecoinspace.org HTTP cagrilari respx ile mock'lanir. Ltub->xpub version-byte
swap, BIP-84 SegWit derivation, gap-limit tarama, 429 retry, error path,
health_check kapsanir. Single-address + temel error path'ler
test_blockchain_simple_rest.py'de mevcut; bu dosya xpub/derivation/health odakli.
"""

from decimal import Decimal

import httpx
import pytest
import respx

from app.services.blockchain.litecoin import (
    LITOSHI_PER_LTC,
    LitecoinService,
    _balance_cache,
    _looks_like_xpub,
    _ltub_to_xpub,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _balance_cache.invalidate()
    yield
    _balance_cache.invalidate()


@pytest.fixture
def _no_sleep(monkeypatch):
    import asyncio

    async def _fast(_s: float = 0) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast)


# Deterministic test keys (seed 00*64, m/84/0/0 account pub).
VALID_XPUB = "xpub6BnJ1otUYB6KUWQbuBUp1P6oVAHKoLrC9sq6QRYnen2HwXT7MFoc6z5i2xvz6D4yZTFhKRhx2UoMBBJ8Dm4zVfxzPjPKDax4mz6XivVhXqB"
VALID_LTUB = "Ltub2YDQUT6WRcQKisgYVfUosFD2ZxbtZ8NLHA35EWHu2Grzfu5v1GJLvda9PqT1kcUE9ffGuZ6VsWSjHGfF8fASLbkQgsGmtGi7GUrsdQPsWoS"
VALID_LTC_ADDR = "ltc1qg4y0amjqejfgyf2vu5fjt7yzh6qmddxqcl9wmu"


# ─── helpers ──────────────────────────────────────────────────────────


def test_looks_like_xpub_prefixes():
    assert _looks_like_xpub("Ltub123")
    assert _looks_like_xpub("Ltpv123")
    assert _looks_like_xpub("xpubABC")
    assert _looks_like_xpub("ypubABC")
    assert _looks_like_xpub("zpubABC")
    assert not _looks_like_xpub("ltc1qxyz")
    assert not _looks_like_xpub("1Abc")


def test_ltub_to_xpub_roundtrip():
    """Ltub -> standart Bitcoin xpub prefix donusumu."""
    converted = _ltub_to_xpub(VALID_LTUB)
    assert converted == VALID_XPUB


def test_ltub_to_xpub_accepts_plain_xpub():
    """Zaten xpub prefix'li raw da kabul edilir."""
    converted = _ltub_to_xpub(VALID_XPUB)
    assert converted == VALID_XPUB


def test_ltub_to_xpub_invalid_prefix_raises():
    """Bilinmeyen base58check prefix -> ValueError."""
    import base58

    bad = base58.b58encode_check(bytes.fromhex("deadbeef") + b"\x00" * 74).decode()
    with pytest.raises(ValueError, match="Gecersiz|Geçersiz"):
        _ltub_to_xpub(bad)


def test_litoshi_constant():
    assert LITOSHI_PER_LTC == Decimal("100000000")


# ─── xpub balance + scan ──────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_xpub_all_empty_zero(_no_sleep):
    respx.get(url__regex=r"https://litecoinspace\.org/api/address/.*").mock(return_value=httpx.Response(200, json={"chain_stats": {"tx_count": 0}}))
    svc = LitecoinService(VALID_LTUB)
    bal = await svc._fetch_xpub_balance(VALID_LTUB)
    assert bal == Decimal("0")


@pytest.mark.asyncio
@respx.mock
async def test_xpub_with_balance(_no_sleep):
    """Ilk adreste bakiye -> toplama eklenir."""
    calls = {"n": 0}

    def _responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={"chain_stats": {"tx_count": 4, "funded_txo_sum": 300_000_000, "spent_txo_sum": 100_000_000}},
            )
        return httpx.Response(200, json={"chain_stats": {"tx_count": 0}})

    respx.get(url__regex=r"https://litecoinspace\.org/api/address/.*").mock(side_effect=_responder)
    svc = LitecoinService(VALID_LTUB)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].symbol == "LTC"
    assert assets[0].liquid_quantity == Decimal("2.0")  # 200M sat


@pytest.mark.asyncio
@respx.mock
async def test_xpub_scan_429_retry(_no_sleep):
    calls = {"n": 0}

    def _responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"chain_stats": {"tx_count": 0}})

    respx.get(url__regex=r"https://litecoinspace\.org/api/address/.*").mock(side_effect=_responder)
    svc = LitecoinService(VALID_LTUB)
    bal = await svc._fetch_xpub_balance(VALID_LTUB)
    assert bal == Decimal("0")
    assert calls["n"] > 1


@pytest.mark.asyncio
@respx.mock
async def test_xpub_scan_http_error_empty(_no_sleep):
    respx.get(url__regex=r"https://litecoinspace\.org/api/address/.*").mock(return_value=httpx.Response(500))
    svc = LitecoinService(VALID_LTUB)
    bal = await svc._fetch_xpub_balance(VALID_LTUB)
    assert bal == Decimal("0")


@pytest.mark.asyncio
async def test_xpub_invalid_raises_valueerror():
    svc = LitecoinService("Ltub_invalid_garbage")
    with pytest.raises(ValueError, match="Litecoin xpub"):
        await svc._fetch_xpub_balance("Ltub_invalid_garbage")


@pytest.mark.asyncio
async def test_plain_xpub_path(_no_sleep):
    """Ltub/Ltpv olmayan xpub dogrudan kullanilir (donusum atlanir)."""
    with respx.mock:
        respx.get(url__regex=r"https://litecoinspace\.org/api/address/.*").mock(return_value=httpx.Response(200, json={"chain_stats": {"tx_count": 0}}))
        svc = LitecoinService(VALID_XPUB)
        bal = await svc._fetch_xpub_balance(VALID_XPUB)
        assert bal == Decimal("0")


# ─── derive_address ───────────────────────────────────────────────────


def test_derive_address_produces_ltc1():
    from bip_utils import Bip32Secp256k1

    node = Bip32Secp256k1.FromExtendedKey(VALID_XPUB)
    addr = LitecoinService._derive_address(node, 0, 0)
    assert addr.startswith("ltc1q")


# ─── fetch error/zero ─────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_500_returns_empty():
    respx.get(f"https://litecoinspace.org/api/address/{VALID_LTC_ADDR}").mock(return_value=httpx.Response(500))
    svc = LitecoinService(VALID_LTC_ADDR)
    assert await svc.fetch() == []


# ─── health_check ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_ltub_true():
    svc = LitecoinService(VALID_LTUB)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_plain_xpub_true():
    svc = LitecoinService(VALID_XPUB)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_invalid_ltub_false():
    svc = LitecoinService("Ltub_bozuk")
    assert await svc.health_check() is False


@pytest.mark.asyncio
@respx.mock
async def test_health_check_single_address_ok():
    respx.get(f"https://litecoinspace.org/api/address/{VALID_LTC_ADDR}").mock(return_value=httpx.Response(200, json={"chain_stats": {}}))
    svc = LitecoinService(VALID_LTC_ADDR)
    assert await svc.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_single_address_500_false():
    respx.get(f"https://litecoinspace.org/api/address/{VALID_LTC_ADDR}").mock(return_value=httpx.Response(500))
    svc = LitecoinService(VALID_LTC_ADDR)
    assert await svc.health_check() is False
