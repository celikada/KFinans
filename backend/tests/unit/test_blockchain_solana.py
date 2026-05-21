"""TEST-001 (FAZ H): services/blockchain/solana.py birim testleri.

JSON-RPC mock'lanir (respx). getBalance + getProgramAccounts (stake)
+ rate limit 429 retry.
"""

from decimal import Decimal

import httpx
import pytest
import respx

from app.services.blockchain.solana import (
    _BALANCE_CACHE,
    LAMPORTS_PER_SOL,
    SolanaService,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    _BALANCE_CACHE.clear()
    yield
    _BALANCE_CACHE.clear()


VALID_SOL_ADDR = "5xrLLzPq3HCoLzWzkZGTzWFA8L8TfFzd9JAa3xYz4Pm"
RPC_URL = "https://api.mainnet-beta.solana.com"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_native_balance_only():
    """Stake yok ise sadece liquid SOL doner."""
    respx.post(RPC_URL).mock(
        side_effect=[
            # getBalance: 5 SOL
            httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": {"value": 5_000_000_000}}
            ),
            # getProgramAccounts (stake offset=12): bos
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": []}),
            # getProgramAccounts (stake offset=44): bos
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": []}),
        ]
    )
    svc = SolanaService(VALID_SOL_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    asset = assets[0]
    assert asset.symbol == "SOL"
    assert asset.liquid_quantity == Decimal("5")
    assert asset.staked_quantity == Decimal("0")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_with_staked_amount():
    """Stake hesabi varsa staked_quantity dolar."""
    respx.post(RPC_URL).mock(
        side_effect=[
            httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": {"value": 1_000_000_000}}
            ),
            # offset=12 (staker): 2 stake account
            httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": [
                        {"pubkey": "stake1", "account": {"lamports": 3_000_000_000}},
                        {"pubkey": "stake2", "account": {"lamports": 2_000_000_000}},
                    ],
                },
            ),
            # offset=44 (withdrawer): zaten ayni hesaplar (dedup test)
            httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": [
                        {"pubkey": "stake1", "account": {"lamports": 3_000_000_000}},
                    ],
                },
            ),
        ]
    )
    svc = SolanaService(VALID_SOL_ADDR)
    bal_lamports, staked_lamports = await svc._cached_balance()
    # _cached_balance raw lamports doner (LAMPORTS_PER_SOL conversion fetch() icinde).
    assert bal_lamports == Decimal("1000000000")  # 1 SOL = 10^9 lamports
    # 3+2 = 5 SOL stake (stake1 dedup edildi -> 3 + 2 = 5e9 lamports)
    assert staked_lamports == Decimal("5000000000")


@pytest.mark.asyncio
@respx.mock
async def test_rpc_error_raises_runtime():
    """RPC 'error' alani RuntimeError uretir."""
    respx.post(RPC_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "Invalid params"},
            },
        )
    )
    svc = SolanaService(VALID_SOL_ADDR)
    with pytest.raises(RuntimeError, match="Solana RPC error"):
        async with httpx.AsyncClient() as client:
            await svc._rpc_call(client, "getBalance", [VALID_SOL_ADDR])


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_429_retries(monkeypatch):
    """429 yanitinda 3 deneme yapilir; sonunda basarili 200 doner.

    asyncio.sleep mock'lanir test gerçek bekleme yapmasin."""
    import asyncio

    sleep_calls = []

    async def _fake_sleep(s: float) -> None:
        sleep_calls.append(s)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    respx.post(RPC_URL).mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(429),
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"value": 100}}),
        ]
    )
    svc = SolanaService(VALID_SOL_ADDR)
    async with httpx.AsyncClient() as client:
        data = await svc._rpc_call(client, "getBalance", [VALID_SOL_ADDR])
    assert data["result"]["value"] == 100
    # 2 fail = 2 sleep
    assert len(sleep_calls) == 2


def test_lamports_per_sol_constant():
    """1 SOL = 10^9 lamports — finansal sabit."""
    assert LAMPORTS_PER_SOL == Decimal(10) ** 9
