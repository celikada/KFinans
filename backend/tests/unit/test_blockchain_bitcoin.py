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
    _BALANCE_CACHE,
    BitcoinService,
)


@pytest.fixture(autouse=True)
def _clear_btc_cache():
    """Module-level cache testler arasi paylasilmasin."""
    _BALANCE_CACHE.clear()
    yield
    _BALANCE_CACHE.clear()


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

    # Cache'i manuel eski'ye al — TTL gecmis sayilsin
    _BALANCE_CACHE[VALID_BTC_ADDR] = (time.monotonic() - 999, Decimal("1.0"))

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
