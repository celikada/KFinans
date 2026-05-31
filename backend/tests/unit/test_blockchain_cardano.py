"""TEST-001: services/blockchain/cardano.py birim testleri.

Koios account_info POST cagrisi respx ile mock'lanir. stake1/addr1 normalize,
addr1 -> stake1 turetimi, utxo + rewards_available -> liquid + pending,
bos rows, zero balance, koios fail, health_check kapsanir.
"""

from decimal import Decimal

import httpx
import pytest
import respx

from app.services.blockchain.cardano import (
    LOVELACE_PER_ADA,
    CardanoService,
    _addr_to_stake,
)

KOIOS_URL = "https://api.koios.rest/api/v1/account_info"

VALID_STAKE = "stake1u9jx2en8dp5k56mvd4hx7ur3wfehgatkwau8j7nm037hulctderj8"
VALID_ADDR1 = "addr1qyqqzqsrqszsvpcgpy9qkrqdpc83qygjzv2p29shrqv35xmyv4nxw6rfdf4kcmtwdac8zunnw36hvamc09a8klra0elsr0jfpr"


def test_lovelace_constant():
    assert LOVELACE_PER_ADA == Decimal("1000000")


# ─── address normalization ────────────────────────────────────────────


def test_normalize_stake1_passthrough():
    assert CardanoService._normalize_to_stake(VALID_STAKE) == VALID_STAKE


def test_normalize_addr1_to_stake():
    """addr1 -> stake1 turetilir (Shelley base address stake credential)."""
    stake = CardanoService._normalize_to_stake(VALID_ADDR1)
    assert stake.startswith("stake1")
    assert stake == VALID_STAKE


def test_normalize_unknown_prefix_raises():
    with pytest.raises(ValueError, match="Bilinmeyen"):
        CardanoService._normalize_to_stake("byron_xyz")


def test_addr_to_stake_too_short_raises():
    """57 byte'tan kisa addr -> ValueError."""
    from bip_utils import Bech32Encoder

    short = Bech32Encoder.Encode("addr", bytes(10))
    with pytest.raises(ValueError, match="57 byte"):
        _addr_to_stake(short)


# ─── fetch happy path ─────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_utxo_and_rewards():
    """utxo -> liquid, rewards_available -> pending_rewards."""
    respx.post(KOIOS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[{"utxo": "9500000", "rewards_available": "500000"}],
        )
    )
    svc = CardanoService(VALID_STAKE)
    assets = await svc.fetch()
    assert len(assets) == 1
    a = assets[0]
    assert a.symbol == "ADA"
    assert a.liquid_quantity == Decimal("9.500000")
    assert a.pending_rewards == Decimal("0.500000")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_via_addr1():
    """addr1 girisi de stake'e cevrilip sorgulanir."""
    respx.post(KOIOS_URL).mock(return_value=httpx.Response(200, json=[{"utxo": "1000000", "rewards_available": "0"}]))
    svc = CardanoService(VALID_ADDR1)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].liquid_quantity == Decimal("1.000000")


# ─── empty / zero / error paths ───────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_fetch_empty_rows_returns_empty():
    """Koios bos liste -> bos donus."""
    respx.post(KOIOS_URL).mock(return_value=httpx.Response(200, json=[]))
    svc = CardanoService(VALID_STAKE)
    assert await svc.fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_zero_balance_returns_empty():
    """utxo=0 + rewards=0 -> bos donus."""
    respx.post(KOIOS_URL).mock(return_value=httpx.Response(200, json=[{"utxo": "0", "rewards_available": "0"}]))
    svc = CardanoService(VALID_STAKE)
    assert await svc.fetch() == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_koios_500_returns_empty():
    respx.post(KOIOS_URL).mock(return_value=httpx.Response(500))
    svc = CardanoService(VALID_STAKE)
    assert await svc.fetch() == []


@pytest.mark.asyncio
async def test_fetch_bad_address_returns_empty():
    """Cozulemeyen adres -> normalize fail -> bos donus (HTTP yapilmaz)."""
    svc = CardanoService("byron_legacy_addr")
    assert await svc.fetch() == []


# ─── health_check ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_valid_stake_true():
    svc = CardanoService(VALID_STAKE)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_invalid_false():
    svc = CardanoService("byron_xyz")
    assert await svc.health_check() is False
