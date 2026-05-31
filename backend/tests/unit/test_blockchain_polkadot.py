"""TEST-001: services/blockchain/polkadot.py birim testleri.

SubstrateInterface (TCP/WS) monkeypatch ile sahte sinifa cevrilir; gercek aga
gidilmez. Relay + Asset Hub paralel sorgu, free/reserved -> liquid/staked,
RPC fail -> 0 fallback, cache, fetch zero/empty, health_check kapsanir.
"""

from decimal import Decimal

import pytest

import app.services.blockchain.polkadot as pk
from app.services.blockchain.polkadot import (
    PLANCK_PER_DOT,
    PolkadotService,
    _balance_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _balance_cache.invalidate()
    yield
    _balance_cache.invalidate()


VALID_DOT_ADDR = "15oF4uVJwmo4TdGW7VfQxNLavjCXviqxT9S1MgbjMNHr6Sp5"


class _FakeResult:
    def __init__(self, free, reserved):
        self.value = {"data": {"free": free, "reserved": reserved}}


class _FakeSubstrate:
    """SubstrateInterface yerine gecen sahte sinif. url'ye gore deger doner."""

    responses: dict[str, tuple[int, int]] = {}
    raise_for: set[str] = set()

    def __init__(self, url: str):
        self.url = url
        if url in self.raise_for:
            raise ConnectionError("RPC down")

    def query(self, module, storage, params):
        free, reserved = self.responses.get(self.url, (0, 0))
        return _FakeResult(free, reserved)


@pytest.fixture
def _patch_substrate(monkeypatch):
    _FakeSubstrate.responses = {}
    _FakeSubstrate.raise_for = set()
    monkeypatch.setattr(pk, "SubstrateInterface", _FakeSubstrate)
    return _FakeSubstrate


def test_planck_constant():
    assert PLANCK_PER_DOT == Decimal("10000000000")


# ─── fetch happy path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_relay_plus_hub_liquid_and_staked(_patch_substrate):
    """Relay free + Hub free -> liquid; relay reserved -> staked."""
    _patch_substrate.responses = {
        pk._RELAY_RPC: (50_000_000_000, 30_000_000_000),  # 5 free, 3 reserved
        pk._ASSET_HUB_RPC: (20_000_000_000, 0),  # 2 free
    }
    svc = PolkadotService(VALID_DOT_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    a = assets[0]
    assert a.symbol == "DOT"
    assert a.liquid_quantity == Decimal("7.0000")  # 5 + 2
    assert a.staked_quantity == Decimal("3.0000")


@pytest.mark.asyncio
async def test_fetch_zero_returns_empty(_patch_substrate):
    """Tum bakiyeler 0 -> bos liste."""
    _patch_substrate.responses = {pk._RELAY_RPC: (0, 0), pk._ASSET_HUB_RPC: (0, 0)}
    svc = PolkadotService(VALID_DOT_ADDR)
    assert await svc.fetch() == []


@pytest.mark.asyncio
async def test_fetch_only_staked(_patch_substrate):
    """Sadece reserved (staked) -> liquid 0 ama liste doner."""
    _patch_substrate.responses = {pk._RELAY_RPC: (0, 10_000_000_000), pk._ASSET_HUB_RPC: (0, 0)}
    svc = PolkadotService(VALID_DOT_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].liquid_quantity == Decimal("0.0000")
    assert assets[0].staked_quantity == Decimal("1.0000")


# ─── RPC fail fallback ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_relay_rpc_fail_returns_zero(_patch_substrate):
    """_sync_query relay fail -> (0,0); sadece hub bakiyesi sayilir."""
    _patch_substrate.raise_for = {pk._RELAY_RPC}
    _patch_substrate.responses = {pk._ASSET_HUB_RPC: (40_000_000_000, 0)}
    svc = PolkadotService(VALID_DOT_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].liquid_quantity == Decimal("4.0000")
    assert assets[0].staked_quantity == Decimal("0.0000")


def test_sync_query_exception_returns_zero(_patch_substrate):
    """_sync_query baglanti hatasinda (0,0) doner, raise etmez."""
    _patch_substrate.raise_for = {pk._RELAY_RPC}
    svc = PolkadotService(VALID_DOT_ADDR)
    free, reserved = svc._sync_query(pk._RELAY_RPC)
    assert free == Decimal(0)
    assert reserved == Decimal(0)


# ─── cache ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_avoids_second_query(_patch_substrate, monkeypatch):
    """Ikinci _cached_balance cache'ten doner — SubstrateInterface tekrar acilmaz."""
    _patch_substrate.responses = {pk._RELAY_RPC: (1_000_000_000, 0), pk._ASSET_HUB_RPC: (0, 0)}
    instances = {"n": 0}
    orig_init = _patch_substrate.__init__

    def _counting_init(self, url):
        instances["n"] += 1
        orig_init(self, url)

    monkeypatch.setattr(_patch_substrate, "__init__", _counting_init)

    svc = PolkadotService(VALID_DOT_ADDR)
    r1 = await svc._cached_balance()
    n_after_first = instances["n"]
    r2 = await svc._cached_balance()
    assert r1 == r2
    assert instances["n"] == n_after_first, "Cache 2. cagrida yeni baglanti acmamali"


# ─── fetch exception graceful ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_unexpected_exception_returns_empty(monkeypatch):
    """_cached_balance beklenmedik exception -> fetch() bos liste."""

    async def _boom(self):
        raise RuntimeError("boom")

    monkeypatch.setattr(PolkadotService, "_cached_balance", _boom)
    svc = PolkadotService(VALID_DOT_ADDR)
    assert await svc.fetch() == []


# ─── health_check ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_true(_patch_substrate):
    _patch_substrate.responses = {pk._RELAY_RPC: (0, 0)}
    svc = PolkadotService(VALID_DOT_ADDR)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_to_thread_exception_false(monkeypatch):
    """asyncio.to_thread raise -> health_check False."""
    import asyncio

    async def _boom(*a, **k):
        raise RuntimeError("thread fail")

    monkeypatch.setattr(asyncio, "to_thread", _boom)
    svc = PolkadotService(VALID_DOT_ADDR)
    assert await svc.health_check() is False
