"""TEST-001 (FAZ H): services/blockchain/bitcoin.py birim testleri.

mempool.space HTTP cagrilari respx ile mock'lanir; gercek aga gidilmez.
xpub HD derivation, single address balance, cache + single-flight pattern,
graceful error handling test edilir.
"""

import time
from decimal import Decimal

import httpx
import pytest
import respx

from app.services.blockchain.bitcoin import (
    BitcoinService,
    _balance_cache,
)


@pytest.fixture(autouse=True)
def _clear_btc_cache():
    """Module-level cache testler arasi paylasilmasin."""
    _balance_cache.invalidate()
    yield
    _balance_cache.invalidate()


VALID_BTC_ADDR = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"


# ─── Single address balance ────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_single_address_balance():
    """funded_txo_sum - spent_txo_sum = balance (satoshi -> BTC)."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(
        return_value=httpx.Response(
            200,
            json={
                "chain_stats": {
                    "funded_txo_sum": 200_000_000,  # 2 BTC funded
                    "spent_txo_sum": 50_000_000,  # 0.5 BTC spent
                    "tx_count": 5,
                }
            },
        )
    )
    svc = BitcoinService(VALID_BTC_ADDR)
    bal = await svc._fetch_single_balance(VALID_BTC_ADDR)
    assert bal == Decimal("1.5")  # (200M - 50M) / 1e8


@pytest.mark.asyncio
@respx.mock
async def test_fetch_single_address_zero_balance():
    """funded == spent -> 0 BTC."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(
        return_value=httpx.Response(
            200,
            json={
                "chain_stats": {"funded_txo_sum": 100_000, "spent_txo_sum": 100_000},
            },
        )
    )
    svc = BitcoinService(VALID_BTC_ADDR)
    bal = await svc._fetch_single_balance(VALID_BTC_ADDR)
    assert bal == Decimal("0")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_single_address_500_raises():
    """5xx HTTP yanit raise_for_status ile exception."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(return_value=httpx.Response(500))
    svc = BitcoinService(VALID_BTC_ADDR)
    with pytest.raises(httpx.HTTPStatusError):
        await svc._fetch_single_balance(VALID_BTC_ADDR)


# ─── Cache + single-flight ─────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_cache_hit_avoids_second_http_call():
    """Ayni address ikinci kez cagrildiginda cache'ten doner — HTTP cagrisi yok."""
    route = respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(
        return_value=httpx.Response(
            200,
            json={
                "chain_stats": {"funded_txo_sum": 100_000_000, "spent_txo_sum": 0},
            },
        )
    )
    svc = BitcoinService(VALID_BTC_ADDR)
    bal1 = await svc._cached_balance()
    bal2 = await svc._cached_balance()
    assert bal1 == bal2 == Decimal("1.0")
    assert route.call_count == 1, "Cache 2. cagrida tekrar HTTP yapmamalı"


@pytest.mark.asyncio
@respx.mock
async def test_cache_expires_after_ttl():
    """Cache TTL gecince yeni HTTP cagrisi yapilir."""
    route = respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(
        return_value=httpx.Response(
            200,
            json={
                "chain_stats": {"funded_txo_sum": 100_000_000, "spent_txo_sum": 0},
            },
        )
    )
    svc = BitcoinService(VALID_BTC_ADDR)
    await svc._cached_balance()

    # Cache'i manuel eski'ye al — TTL gecmis sayilsin (private _cache dict'i ile).
    # TTL 1800s (30 dk); bu degerin uzerinde bir yas ver.
    _balance_cache._cache[VALID_BTC_ADDR] = (time.monotonic() - 9999, Decimal("1.0"))

    await svc._cached_balance()
    assert route.call_count == 2, "TTL gectikten sonra yeni HTTP cagrisi olmali"


# ─── fetch() entegrasyon ──────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_asset_data_with_balance():
    """fetch() AssetData listesi doner; symbol=BTC, liquid_quantity=balance."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(
        return_value=httpx.Response(
            200,
            json={
                "chain_stats": {"funded_txo_sum": 250_000_000, "spent_txo_sum": 50_000_000},
            },
        )
    )
    svc = BitcoinService(VALID_BTC_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    asset = assets[0]
    assert asset.symbol == "BTC"
    assert asset.liquid_quantity == Decimal("2.0")
    assert asset.asset_type == "crypto"


# ─── xpub validation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_xpub_raises_valueerror():
    """Bozuk xpub stringi ValueError."""
    svc = BitcoinService("xpub_invalid_garbage")
    with pytest.raises(ValueError, match="xpub"):
        await svc._fetch_xpub_balance("xpub_invalid_garbage")


# ─── xpub HD derivation + scan ────────────────────────────────────────


# Deterministic test xpub (seed 00*64, BIP-84 m/84/0/0 account-level pub).
VALID_XPUB = "xpub6BnJ1otUYB6KUWQbuBUp1P6oVAHKoLrC9sq6QRYnen2HwXT7MFoc6z5i2xvz6D4yZTFhKRhx2UoMBBJ8Dm4zVfxzPjPKDax4mz6XivVhXqB"


@pytest.fixture
def _no_sleep(monkeypatch):
    """xpub tarama icindeki asyncio.sleep gercek beklemesin."""
    import asyncio

    async def _fast(_s: float = 0) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast)


@pytest.mark.asyncio
@respx.mock
async def test_xpub_all_empty_returns_zero(_no_sleep):
    """Tum turetilen adresler tx_count=0 -> gap_limit ile biter, 0 BTC.

    SegWit bos -> Legacy de taranir, ama hepsi bos."""
    respx.get(url__regex=r"https://mempool\.space/api/address/.*").mock(
        return_value=httpx.Response(200, json={"chain_stats": {"tx_count": 0, "funded_txo_sum": 0, "spent_txo_sum": 0}})
    )
    svc = BitcoinService(VALID_XPUB)
    bal = await svc._fetch_xpub_balance(VALID_XPUB)
    assert bal == Decimal("0")


@pytest.mark.asyncio
@respx.mock
async def test_xpub_segwit_active_with_balance(_no_sleep):
    """Ilk SegWit adresinde bakiye var -> Legacy taranmaz (segwit_active)."""
    calls = {"n": 0}

    def _responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            # ilk adres (receive idx 0): bakiyeli
            return httpx.Response(
                200,
                json={"chain_stats": {"tx_count": 3, "funded_txo_sum": 100_000_000, "spent_txo_sum": 0}},
            )
        # geri kalan adresler bos
        return httpx.Response(200, json={"chain_stats": {"tx_count": 0, "funded_txo_sum": 0, "spent_txo_sum": 0}})

    respx.get(url__regex=r"https://mempool\.space/api/address/.*").mock(side_effect=_responder)
    svc = BitcoinService(VALID_XPUB)
    bal = await svc._fetch_xpub_balance(VALID_XPUB)
    assert bal == Decimal("1.0")


@pytest.mark.asyncio
@respx.mock
async def test_xpub_scan_429_then_success(_no_sleep):
    """429 ilk adreste -> ayni index retry, sonra 200 bos doner."""
    calls = {"n": 0}

    def _responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"chain_stats": {"tx_count": 0}})

    respx.get(url__regex=r"https://mempool\.space/api/address/.*").mock(side_effect=_responder)
    svc = BitcoinService(VALID_XPUB)
    bal = await svc._fetch_xpub_balance(VALID_XPUB)
    assert bal == Decimal("0")
    # 429 retry yapildi -> en az 1 ekstra cagri
    assert calls["n"] > 1


@pytest.mark.asyncio
@respx.mock
async def test_xpub_scan_http_error_counts_as_empty(_no_sleep):
    """Adres sorgusu 500 -> except dali empty_streak++ ile devam, 0 doner."""
    respx.get(url__regex=r"https://mempool\.space/api/address/.*").mock(return_value=httpx.Response(500))
    svc = BitcoinService(VALID_XPUB)
    bal = await svc._fetch_xpub_balance(VALID_XPUB)
    assert bal == Decimal("0")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_xpub_via_fetch_returns_assetdata(_no_sleep):
    """fetch() xpub adresiyle: ilk adreste bakiye -> AssetData."""

    calls = {"n": 0}

    def _responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={"chain_stats": {"tx_count": 2, "funded_txo_sum": 50_000_000, "spent_txo_sum": 0}},
            )
        return httpx.Response(200, json={"chain_stats": {"tx_count": 0}})

    respx.get(url__regex=r"https://mempool\.space/api/address/.*").mock(side_effect=_responder)
    svc = BitcoinService(VALID_XPUB)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].symbol == "BTC"
    assert assets[0].liquid_quantity == Decimal("0.5")


# ─── fetch() error/zero paths ─────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_on_http_error():
    """_cached_balance exception -> fetch() bos liste (snapshot bozulmasin)."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(return_value=httpx.Response(503))
    svc = BitcoinService(VALID_BTC_ADDR)
    assert await svc.fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_on_zero_balance():
    """Bakiye 0 -> fetch() bos liste."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(
        return_value=httpx.Response(200, json={"chain_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0}})
    )
    svc = BitcoinService(VALID_BTC_ADDR)
    assert await svc.fetch() == []


# ─── derive_address ───────────────────────────────────────────────────


def test_derive_address_segwit_vs_legacy():
    """_derive_address segwit=True -> bc1q..., False -> 1... (Legacy P2PKH)."""
    from bip_utils import Bip32Secp256k1

    node = Bip32Secp256k1.FromExtendedKey(VALID_XPUB)
    segwit = BitcoinService._derive_address(node, 0, 0, True)
    legacy = BitcoinService._derive_address(node, 0, 0, False)
    assert segwit.startswith("bc1q")
    assert legacy.startswith("1")


# ─── health_check ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_valid_xpub_true():
    """Gecerli xpub -> HTTP'siz True."""
    svc = BitcoinService(VALID_XPUB)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_invalid_xpub_false():
    """Bozuk xpub -> False."""
    svc = BitcoinService("xpub_bozuk")
    assert await svc.health_check() is False


@pytest.mark.asyncio
@respx.mock
async def test_health_check_single_address_ok():
    """Tek adres 200 -> True."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(return_value=httpx.Response(200, json={"chain_stats": {}}))
    svc = BitcoinService(VALID_BTC_ADDR)
    assert await svc.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_single_address_500_false():
    """Tek adres 500 -> False."""
    respx.get(f"https://mempool.space/api/address/{VALID_BTC_ADDR}").mock(return_value=httpx.Response(500))
    svc = BitcoinService(VALID_BTC_ADDR)
    assert await svc.health_check() is False
