"""Avalanche P-Chain servisi + evm_tokens ek dal testleri.

P-Chain Glacier REST + JSON-RPC fallback httpx tabanli -> respx mock.
Cache (AsyncTTLCache) testler arasi temizlenir. _to_decimal_navax /
_sum_assets pure helper'lari da test edilir.
"""

from decimal import Decimal

import httpx
import pytest
import respx
from web3 import AsyncWeb3

import app.services.blockchain.avalanche as avalanche_mod
from app.config import settings
from app.services.blockchain.avalanche import AvalanchePChainService
from app.services.blockchain.evm_tokens import (
    ERC20_ABI,
    TokenDef,
    fetch_token_balances,
)

GLACIER_URL = "https://glacier-api.avax.network/v1/networks/mainnet/blockchains/p-chain/balances"
P_ADDR = "avax1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqaaaaaa"


@pytest.fixture(autouse=True)
def _clear_pchain_cache():
    avalanche_mod._pchain_cache.invalidate()
    yield
    avalanche_mod._pchain_cache.invalidate()


# ─── _to_decimal_navax pure helper ─────────────────────────────────────


def test_to_decimal_navax_none():
    assert AvalanchePChainService._to_decimal_navax(None) == Decimal(0)


def test_to_decimal_navax_int():
    # 1 AVAX = 1e9 nAVAX
    assert AvalanchePChainService._to_decimal_navax(1_000_000_000) == Decimal("1")


def test_to_decimal_navax_decimal_string():
    assert AvalanchePChainService._to_decimal_navax("2000000000") == Decimal("2")


def test_to_decimal_navax_hex_string():
    # 0x3b9aca00 = 1_000_000_000
    assert AvalanchePChainService._to_decimal_navax("0x3b9aca00") == Decimal("1")


# ─── _sum_assets pure helper ────────────────────────────────────────────


def test_sum_assets_non_dict_returns_zero():
    assert AvalanchePChainService._sum_assets(None) == Decimal(0)
    assert AvalanchePChainService._sum_assets([]) == Decimal(0)


def test_sum_assets_sums_mapping_values():
    mapping = {"avax": 1_000_000_000, "avax2": 500_000_000}
    assert AvalanchePChainService._sum_assets(mapping) == Decimal("1.5")


# ─── fetch via Glacier (happy path) ────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_pchain_fetch_via_glacier_liquid_and_staked():
    respx.get(GLACIER_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": {
                    "unlockedUnstaked": [{"symbol": "AVAX", "amount": "5000000000"}],  # 5 AVAX
                    "lockedStaked": [{"denomination": 9, "amount": "3000000000"}],  # 3 AVAX
                    "pendingStaked": [{"symbol": "AVAX", "amount": "1000000000"}],  # 1 AVAX
                    "unlockedStaked": [],
                    "lockedStakeable": [],
                }
            },
        )
    )
    svc = AvalanchePChainService(P_ADDR, wallet_address_id="wp")
    assets = await svc.fetch()
    assert len(assets) == 1
    a = assets[0]
    assert a.symbol == "AVAX"
    assert a.provider == "avalanche_p"
    assert a.liquid_quantity == Decimal("5")
    assert a.staked_quantity == Decimal("4")  # 3 + 1
    assert a.asset_type == "crypto"  # liquid (5) >= staked (4)
    assert a.wallet_address_id == "wp"


@pytest.mark.asyncio
@respx.mock
async def test_pchain_staked_greater_marks_staked_crypto():
    respx.get(GLACIER_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": {
                    "unlockedUnstaked": [{"symbol": "AVAX", "amount": "1000000000"}],  # 1
                    "lockedStaked": [{"symbol": "AVAX", "amount": "10000000000"}],  # 10
                }
            },
        )
    )
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets[0].asset_type == "staked_crypto"


@pytest.mark.asyncio
@respx.mock
async def test_pchain_zero_balance_returns_empty():
    respx.get(GLACIER_URL).mock(return_value=httpx.Response(200, json={"balances": {"unlockedUnstaked": []}}))
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets == []


@pytest.mark.asyncio
@respx.mock
async def test_pchain_glacier_ignores_non_avax_entries():
    """denomination != 9 ve symbol != AVAX entry'ler atlanir."""
    respx.get(GLACIER_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": {
                    "unlockedUnstaked": [
                        {"symbol": "USDC", "denomination": 6, "amount": "9999"},  # atlanir
                        {"symbol": "AVAX", "amount": "2000000000"},  # 2 AVAX
                    ],
                }
            },
        )
    )
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets[0].liquid_quantity == Decimal("2")


# ─── Glacier fail -> JSON-RPC fallback ─────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_pchain_glacier_fail_falls_back_to_rpc():
    """Glacier 500 -> platform.getBalance + getStake JSON-RPC fallback."""
    respx.get(GLACIER_URL).mock(return_value=httpx.Response(500))

    rpc_url = settings.avalanche_p_api_url

    def _rpc_dispatch(request):
        body = request.content.decode()
        if "getBalance" in body:
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"unlocked": "4000000000"}},  # 4 AVAX
            )
        # getStake
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 2, "result": {"staked": "2000000000"}},  # 2 AVAX
        )

    respx.post(rpc_url).mock(side_effect=_rpc_dispatch)

    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets[0].liquid_quantity == Decimal("4")
    assert assets[0].staked_quantity == Decimal("2")


@pytest.mark.asyncio
@respx.mock
async def test_pchain_rpc_uses_unlockeds_mapping():
    """Yeni API: balance_data.unlockeds + lockedStakeables mapping kullanilir."""
    respx.get(GLACIER_URL).mock(return_value=httpx.Response(503))
    rpc_url = settings.avalanche_p_api_url

    def _rpc_dispatch(request):
        body = request.content.decode()
        if "getBalance" in body:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "unlockeds": {"avax": "6000000000"},  # 6 AVAX
                        "lockedStakeables": {"avax": "1000000000"},  # 1 AVAX
                    },
                },
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"staked": "0"}})

    respx.post(rpc_url).mock(side_effect=_rpc_dispatch)
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets[0].liquid_quantity == Decimal("6")
    assert assets[0].staked_quantity == Decimal("1")  # 0 staked + 1 lockedStakeable


@pytest.mark.asyncio
@respx.mock
async def test_pchain_rpc_429_retry(monkeypatch):
    """JSON-RPC 429 -> backoff retry; sonunda 200."""
    import asyncio

    async def _fake_sleep(s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    respx.get(GLACIER_URL).mock(return_value=httpx.Response(500))
    rpc_url = settings.avalanche_p_api_url

    responses = {"getBalance": [httpx.Response(429), httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"unlocked": "3000000000"}})]}
    state = {"getBalance": 0}

    def _dispatch(request):
        body = request.content.decode()
        if "getBalance" in body:
            i = state["getBalance"]
            state["getBalance"] += 1
            return responses["getBalance"][i]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"staked": "0"}})

    respx.post(rpc_url).mock(side_effect=_dispatch)
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets[0].liquid_quantity == Decimal("3")


@pytest.mark.asyncio
@respx.mock
async def test_pchain_rpc_persistent_429_exhausts_and_fails(monkeypatch):
    """Glacier fail + JSON-RPC 3x 429 -> retry tukenir, raise -> fetch bos doner."""
    import asyncio

    async def _fake_sleep(s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    respx.get(GLACIER_URL).mock(return_value=httpx.Response(500))
    respx.post(settings.avalanche_p_api_url).mock(return_value=httpx.Response(429))
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets == []


@pytest.mark.asyncio
@respx.mock
async def test_pchain_both_fail_returns_empty():
    """Glacier + JSON-RPC ikisi de patlar -> bos liste (fetch try/except)."""
    respx.get(GLACIER_URL).mock(return_value=httpx.Response(500))
    respx.post(settings.avalanche_p_api_url).mock(return_value=httpx.Response(500))
    svc = AvalanchePChainService(P_ADDR)
    assets = await svc.fetch()
    assert assets == []


@pytest.mark.asyncio
@respx.mock
async def test_pchain_cache_avoids_second_call():
    """Ayni adres 2. fetch -> cache hit, HTTP yok."""
    route = respx.get(GLACIER_URL).mock(
        return_value=httpx.Response(
            200,
            json={"balances": {"unlockedUnstaked": [{"symbol": "AVAX", "amount": "1000000000"}]}},
        )
    )
    svc = AvalanchePChainService(P_ADDR)
    await svc.fetch()
    await svc.fetch()
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_pchain_health_check_true():
    respx.post(settings.avalanche_p_api_url).mock(return_value=httpx.Response(200, json={"result": {"height": "1"}}))
    svc = AvalanchePChainService(P_ADDR)
    assert await svc.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_pchain_health_check_false_on_error():
    respx.post(settings.avalanche_p_api_url).mock(side_effect=httpx.ConnectError("down"))
    svc = AvalanchePChainService(P_ADDR)
    assert await svc.health_check() is False


# ─── evm_tokens.fetch_token_balances (curated, web3 contract) ──────────


class _FakeBalanceFn:
    def __init__(self, raw, exc=None):
        self._raw = raw
        self._exc = exc

    def __call__(self, *args):
        return self

    async def call(self):
        if self._exc is not None:
            raise self._exc
        return self._raw


class _FakeFunctions:
    def __init__(self, raw, exc):
        self._raw = raw
        self._exc = exc

    def balanceOf(self, owner):  # noqa: N802
        return _FakeBalanceFn(self._raw, self._exc)


class _FakeContract:
    def __init__(self, raw, exc):
        self.functions = _FakeFunctions(raw, exc)


class _FakeW3Eth:
    def __init__(self, raw_per_token):
        self._raw_per_token = raw_per_token

    def contract(self, address=None, abi=None):
        return _FakeContract(self._raw_per_token, None)


class _FakeW3:
    def __init__(self, raw_per_token):
        self.eth = _FakeW3Eth(raw_per_token)


@pytest.mark.asyncio
async def test_fetch_token_balances_returns_nonzero(monkeypatch):
    """balanceOf > 0.000001 -> token listeye eklenir."""
    import asyncio

    async def _fake_sleep(s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    tokens = [TokenDef("sAVAX", "Staked AVAX", "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", 18)]
    w3 = _FakeW3(raw_per_token=5 * 10**18)  # 5 sAVAX
    out = await fetch_token_balances(w3, "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", tokens)
    assert len(out) == 1
    assert out[0][0].symbol == "sAVAX"
    assert out[0][1] == Decimal("5")


@pytest.mark.asyncio
async def test_fetch_token_balances_skips_dust(monkeypatch):
    """Dust (<= 0.000001) atlanir."""
    import asyncio

    async def _fake_sleep(s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    tokens = [TokenDef("USDC", "USD Coin", "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e", 6)]
    w3 = _FakeW3(raw_per_token=1)  # 1 / 1e6 = 1e-6 -> dust
    out = await fetch_token_balances(w3, "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", tokens)
    assert out == []


@pytest.mark.asyncio
async def test_fetch_token_balances_rate_limit_retry(monkeypatch):
    """'rate' iceren hata -> backoff + retry; sonunda basarili."""
    import asyncio

    sleeps = []

    async def _fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    state = {"n": 0}

    class _FlakyFn:
        def __call__(self, *a):
            return self

        async def call(self):
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("rate limit exceeded")
            return 2 * 10**18

    class _Funcs:
        def balanceOf(self, owner):  # noqa: N802
            return _FlakyFn()

    class _Contract:
        functions = _Funcs()

    class _Eth:
        def contract(self, address=None, abi=None):
            return _Contract()

    class _W3:
        eth = _Eth()

    tokens = [TokenDef("sAVAX", "Staked AVAX", "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", 18)]
    out = await fetch_token_balances(_W3(), "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", tokens)
    assert out[0][1] == Decimal("2")
    assert len(sleeps) >= 1  # en az 1 backoff


@pytest.mark.asyncio
async def test_fetch_token_balances_non_retryable_error_breaks(monkeypatch):
    """Retry edilemeyen hata (ornek: revert) -> token atlanir, break."""
    import asyncio

    async def _fake_sleep(s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    tokens = [TokenDef("BAD", "Bad Token", "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", 18)]
    w3 = _FakeW3(raw_per_token=0)
    # raw=0 yerine exception firlat
    w3.eth = _FakeW3Eth(0)

    class _ErrFn:
        def __call__(self, *a):
            return self

        async def call(self):
            raise RuntimeError("execution reverted")

    class _Funcs:
        def balanceOf(self, owner):  # noqa: N802
            return _ErrFn()

    class _Contract:
        functions = _Funcs()

    class _Eth:
        def contract(self, address=None, abi=None):
            return _Contract()

    class _W3b:
        eth = _Eth()

    out = await fetch_token_balances(_W3b(), "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", tokens)
    assert out == []


def test_erc20_abi_has_balanceof():
    """ABI balanceOf fonksiyonunu icermeli."""
    names = {f.get("name") for f in ERC20_ABI}
    assert "balanceOf" in names


def test_to_checksum_works_for_curated_contracts():
    """Curated token kontratlari gercek checksum'lanabilir (web3 sanity)."""
    for t in avalanche_mod.AVALANCHE_C_TOKENS:
        assert AsyncWeb3.to_checksum_address(t.contract)
