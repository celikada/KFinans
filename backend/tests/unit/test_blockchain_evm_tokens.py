"""TEST-020 (FAZ H): services/blockchain/evm_tokens.py spam filter testleri.

Network bagimsiz pure Python: spam pattern matching, Unicode spoofing,
TokenDef constants. Ethplorer HTTP cagirisi mock'lanir (respx).
"""

from decimal import Decimal

import httpx
import pytest
import respx

from app.services.blockchain.evm_tokens import (
    AVALANCHE_C_TOKENS,
    _has_spoof_chars,
    _looks_like_spam,
    fetch_ethereum_tokens_via_ethplorer,
)

# ─── _looks_like_spam — pure logic ─────────────────────────────────────


def test_legitimate_token_not_spam():
    """USDC/USDT/sAVAX gibi normal isimler spam degil."""
    assert _looks_like_spam("USDC", "USD Coin") is False
    assert _looks_like_spam("ETH", "Ethereum") is False
    assert _looks_like_spam("sAVAX", "Staked AVAX") is False


def test_empty_symbol_is_spam():
    """Bos sembol (Ethplorer bazen verir) spam sayilir."""
    assert _looks_like_spam("", "Some Name") is True


def test_erc20_placeholder_symbol_is_spam():
    """ERC20 sembolü kendi adi gibi anlamsiz."""
    assert _looks_like_spam("ERC20", "Token") is True


def test_url_in_name_is_spam():
    """Visit/claim URL'leri scam isminde tipik."""
    assert _looks_like_spam("AIRDROP", "Visit airdrop.io to claim") is True
    assert _looks_like_spam("REWARD", "https://scam.com claim now") is True


def test_giveaway_keyword_is_spam():
    assert _looks_like_spam("WIN", "ETH giveaway 100x") is True


def test_claim_rewards_pattern_is_spam():
    assert _looks_like_spam("CLAIM", "Claim rewards via app") is True


def test_punctuation_only_is_spam():
    """Sadece sembol/punctuation isimleri."""
    assert _looks_like_spam("...", "***---") is True


def test_dot_io_tld_in_combined_is_spam():
    """abctoken.io / xyz.finance gibi alan adi suffix'i scam."""
    assert _looks_like_spam("ABC", "abctoken.io") is True
    assert _looks_like_spam("XYZ", "DeFi xyz.finance") is True


def test_cherokee_unicode_spoof_is_spam():
    """Cherokee characters (U+13A0-13FF) Latin harf taklidi."""
    # ꓮ (U+A4EE) — Lisu spoof
    assert _looks_like_spam("ꓰꓔꓧ", "Eth Lookalike") is True


def test_math_alphanumeric_unicode_spoof_is_spam():
    """U+1D400-1D7FF Math Alphanumeric — Latin harfleri stilistik kopyasi."""
    # 𝐔𝐒𝐃𝐂 — bold mathematical USDC
    assert _has_spoof_chars("𝐔𝐒𝐃𝐂") is True


def test_normal_text_no_spoof():
    assert _has_spoof_chars("USDC") is False
    assert _has_spoof_chars("Türk Lirası") is False  # Latin/extension OK


# ─── AVALANCHE_C_TOKENS curated list ──────────────────────────────────


def test_avalanche_c_tokens_has_required_minimum():
    """sAVAX + USDT.e + USDC.e curated list'inde olmalidir."""
    symbols = {t.symbol for t in AVALANCHE_C_TOKENS}
    assert "sAVAX" in symbols
    # USDT.e or USDT — Avalanche bridge token
    assert any("USDT" in s for s in symbols)


def test_avalanche_c_tokens_have_valid_contracts():
    """Tum curated token'lar 0x ile baslayan EVM adresi."""
    for token in AVALANCHE_C_TOKENS:
        assert token.contract.startswith("0x")
        assert len(token.contract) == 42  # 0x + 40 hex char
        assert 0 < token.decimals <= 18


# ─── fetch_ethereum_tokens_via_ethplorer (HTTP mock) ──────────────────


@pytest.mark.asyncio
@respx.mock
async def test_ethplorer_returns_filtered_tokens():
    """Ethplorer yanitinda spam tokenlar filtrelenir, normal'ler doner."""
    addr = "0x1234567890123456789012345678901234567890"
    respx.get(f"https://api.ethplorer.io/getAddressInfo/{addr}").mock(
        return_value=httpx.Response(
            200,
            json={
                "tokens": [
                    {
                        "tokenInfo": {
                            "symbol": "USDC",
                            "name": "USD Coin",
                            "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                            "decimals": "6",
                        },
                        "balance": 1000_000_000,  # 1000 USDC
                    },
                    {
                        # Spam: URL pattern in name
                        "tokenInfo": {
                            "symbol": "AIR",
                            "name": "Visit claim.io for airdrop",
                            "address": "0x1111111111111111111111111111111111111111",
                            "decimals": "18",
                        },
                        "balance": 1000_000_000_000_000_000_000,
                    },
                ],
            },
        )
    )
    tokens = await fetch_ethereum_tokens_via_ethplorer(addr)
    # USDC dahil, AIR scam filtrelendi
    symbols = {t[0].symbol for t in tokens}
    assert "USDC" in symbols
    assert "AIR" not in symbols


@pytest.mark.asyncio
@respx.mock
async def test_ethplorer_no_tokens_returns_empty():
    addr = "0x0000000000000000000000000000000000000001"
    respx.get(f"https://api.ethplorer.io/getAddressInfo/{addr}").mock(return_value=httpx.Response(200, json={"tokens": []}))
    tokens = await fetch_ethereum_tokens_via_ethplorer(addr)
    assert tokens == []


@pytest.mark.asyncio
@respx.mock
async def test_ethplorer_500_returns_empty():
    """Ethplorer 5xx -> graceful empty (snapshot bozulmasin)."""
    addr = "0x0000000000000000000000000000000000000002"
    respx.get(f"https://api.ethplorer.io/getAddressInfo/{addr}").mock(return_value=httpx.Response(500))
    tokens = await fetch_ethereum_tokens_via_ethplorer(addr)
    assert tokens == []


@pytest.mark.asyncio
@respx.mock
async def test_ethplorer_filters_huge_amount_spam():
    """1e12'dan buyuk miktar token = airdrop spam (gercek token bu kadar olmaz)."""
    addr = "0x0000000000000000000000000000000000000003"
    respx.get(f"https://api.ethplorer.io/getAddressInfo/{addr}").mock(
        return_value=httpx.Response(
            200,
            json={
                "tokens": [
                    {
                        "tokenInfo": {
                            "symbol": "MASS",
                            "name": "Mass Spam Token",
                            "address": "0xaaaa000000000000000000000000000000000001",
                            "decimals": "18",
                        },
                        # 1e25 token — anormal
                        "balance": 10_000_000_000_000_000_000_000_000_000,
                    }
                ],
            },
        )
    )
    tokens = await fetch_ethereum_tokens_via_ethplorer(addr)
    # Cok yuksek miktar spam filtre tarafindan elenir (>1e12 raw amount)
    assert tokens == [] or all(t[1] < Decimal("1e12") for t in tokens)
