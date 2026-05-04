"""EVM zincirleri için ERC-20 token tarama.

Ethereum: Ethplorer free API (https://ethplorer.io) ile kullanıcının tüm
token bakiyeleri dinamik çekilir, airdrop spam'ı isim pattern'leriyle filtrelenir.

Avalanche C: curated TokenDef listesi (Ethplorer ETH-only). En önemli
sAVAX + popüler stablecoin'ler.
"""
import logging
import re
from decimal import Decimal
from typing import NamedTuple

import httpx
from web3 import AsyncWeb3

logger = logging.getLogger(__name__)

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


class TokenDef(NamedTuple):
    symbol: str
    name: str
    contract: str
    decimals: int


# Spam token tespit pattern'leri — airdrop/scam tokenları filtrele
_SPAM_PATTERNS = [
    re.compile(r"\bvisit\b.*\.(com|org|io|fi|us|net|finance)", re.IGNORECASE),
    re.compile(r"claim\s+rewards?", re.IGNORECASE),
    re.compile(r"airdrop", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"giveaway", re.IGNORECASE),
    re.compile(r"^[\W_]+$"),  # Sadece sembol/punctuation
    re.compile(r"\.(io|com|org|finance|network|fi|us|net|fund|farm)\b", re.IGNORECASE),
]
_SPAM_SYMBOLS = {"ERC20", ""}


def _has_spoof_chars(text: str) -> bool:
    """Cherokee veya Mathematical Alphanumeric Symbols Unicode block'undaki
    karakterler scam token isimlerinde Latin harfleri taklit etmek için
    kullanılır (örn. 'ꓮꓚꓚꓰꓢꓢ' = 'ACCESS' görünümlü)."""
    for ch in text:
        cp = ord(ch)
        if 0x13A0 <= cp <= 0x13FF:  # Cherokee
            return True
        if 0xAB70 <= cp <= 0xABBF:  # Cherokee Supplement
            return True
        if 0x1D400 <= cp <= 0x1D7FF:  # Math Alphanumeric Symbols
            return True
        if 0xA4D0 <= cp <= 0xA4FF:  # Lisu (also used in spoofs)
            return True
    return False


def _looks_like_spam(symbol: str, name: str) -> bool:
    if not symbol or symbol in _SPAM_SYMBOLS:
        return True
    combined = f"{symbol} {name}"
    if _has_spoof_chars(combined):
        return True
    for pat in _SPAM_PATTERNS:
        if pat.search(combined):
            return True
    return False


# Avalanche C-Chain — curated (Ethplorer kapsamı yok)
AVALANCHE_C_TOKENS: list[TokenDef] = [
    TokenDef(
        symbol="sAVAX", name="Benqi Liquid Staked AVAX",
        contract="0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE",
        decimals=18,
    ),
    TokenDef(
        symbol="USDT", name="Tether USD (Avalanche)",
        contract="0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
        decimals=6,
    ),
    TokenDef(
        symbol="USDC", name="USD Coin (Avalanche)",
        contract="0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        decimals=6,
    ),
]


async def fetch_token_balances(
    w3: AsyncWeb3,
    address: str,
    tokens: list[TokenDef],
) -> list[tuple[TokenDef, Decimal]]:
    """Curated token listesi için bakiyeleri sırayla çeker. Avalanche için."""
    import asyncio

    checksum = AsyncWeb3.to_checksum_address(address)
    out: list[tuple[TokenDef, Decimal]] = []

    for token in tokens:
        contract = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(token.contract),
            abi=ERC20_ABI,
        )
        for attempt in range(3):
            try:
                raw = await contract.functions.balanceOf(checksum).call()
                amount = Decimal(raw) / Decimal(10 ** token.decimals)
                if amount > Decimal("0.000001"):
                    out.append((token, amount))
                break
            except Exception as exc:
                msg = str(exc).lower()
                if "rate" in msg or "429" in msg or "header not found" in msg or "connection" in msg:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                logger.debug("Token %s balanceOf hata: %s", token.symbol, exc)
                break
        await asyncio.sleep(0.15)
    return out


async def fetch_ethereum_tokens_via_ethplorer(address: str) -> list[tuple[TokenDef, Decimal]]:
    """Ethplorer free API ile kullanıcının ETH chain'deki tüm tokenlarını çeker.

    Free key 'freekey' günlük ~50 istek limit — dashboard cache + snapshot
    kombosu için yeterli. Spam tokenlar isim pattern'iyle filtrelenir.
    USD değeri olmayan tokenlar (price.rate yok veya 0) da atlanır.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"https://api.ethplorer.io/getAddressInfo/{address}",
                params={"apiKey": "freekey"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Ethplorer ile ETH token tarama başarısız [%s]: %s", address[:12], exc)
        return []

    out: list[tuple[TokenDef, Decimal]] = []
    for t in data.get("tokens", []) or []:
        ti = t.get("tokenInfo") or {}
        symbol = ti.get("symbol", "") or ""
        name = ti.get("name", "") or ""
        if _looks_like_spam(symbol, name):
            continue
        contract = ti.get("address", "")
        try:
            decimals = int(ti.get("decimals", 18))
            raw_balance = Decimal(str(t.get("balance", 0)))
            amount = raw_balance / Decimal(10 ** decimals)
        except Exception:
            continue
        # Anlamsız büyük miktar (airdrop spam pattern: tüm arz tek kullanıcıda)
        if amount > Decimal("1e12"):
            continue
        if amount <= Decimal("0.000001"):
            continue
        out.append((TokenDef(symbol=symbol, name=name, contract=contract, decimals=decimals), amount))
    return out
