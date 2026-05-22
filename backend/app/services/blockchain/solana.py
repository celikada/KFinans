"""Solana cüzdan bakiye servisi.

Native SOL bakiyesi + stake hesaplarındaki delegasyonu toplar.
- Native: `getBalance` RPC (lamports → SOL)
- Stake: `getProgramAccounts` ile kullanıcının withdrawer authority'siyle
  açılmış stake hesapları taranır, her birinin delegated stake'i toplanır.

Public RPC: api.mainnet-beta.solana.com (rate limit ~10 req/s).
Cache + single-flight pattern (Bitcoin servisinden) — dashboard'ın paralel
yenilemeleri RPC'ye yağmasın.
"""

import asyncio
import logging
from decimal import Decimal

import httpx

from app.core.cache import AsyncTTLCache
from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = Decimal("1000000000")  # 10^9
_RPC_URL = "https://api.mainnet-beta.solana.com"
_STAKE_PROGRAM = "Stake11111111111111111111111111111111111111"

# Cache: address → (liquid_lamports, staked_lamports). Public RPC rate-limit'i
# (~10 req/s) için tek paralel tarama; dashboard paralel yenilemeleri sıraya
# girer.
_balance_cache: AsyncTTLCache[tuple[Decimal, Decimal]] = AsyncTTLCache(ttl_sec=600)


class SolanaService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        try:
            liquid_lamports, staked_lamports = await self._cached_balance()
        except Exception as exc:
            logger.warning("Solana bakiye alınamadı [%s]: %s", self.address[:16], exc)
            return []

        liquid_sol = (liquid_lamports / LAMPORTS_PER_SOL).quantize(Decimal("0.000000001"))
        staked_sol = (staked_lamports / LAMPORTS_PER_SOL).quantize(Decimal("0.000000001"))

        if liquid_sol <= 0 and staked_sol <= 0:
            return []

        return [
            AssetData(
                symbol="SOL",
                name="Solana",
                provider="solana",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=liquid_sol,
                staked_quantity=staked_sol,
                wallet_address_id=self.wallet_address_id,
            )
        ]

    async def _cached_balance(self) -> tuple[Decimal, Decimal]:
        async def _fetch() -> tuple[Decimal, Decimal]:
            async with httpx.AsyncClient(timeout=20) as client:
                liquid = await self._get_balance(client, self.address)
                staked = await self._get_staked_total(client, self.address)
            return (liquid, staked)

        return await _balance_cache.get_or_compute(self.address, _fetch)

    @staticmethod
    async def _rpc_call(client: httpx.AsyncClient, method: str, params: list) -> dict:
        """Rate limit (429) için 3 retry exponential backoff."""
        for attempt in range(3):
            resp = await client.post(
                _RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params,
                },
            )
            if resp.status_code == 429:
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Solana RPC error ({method}): {data['error']}")
            return data
        raise RuntimeError(f"Solana {method} 3 deneme sonrası 429 kaldı")

    @classmethod
    async def _get_balance(cls, client: httpx.AsyncClient, address: str) -> Decimal:
        data = await cls._rpc_call(client, "getBalance", [address])
        return Decimal(str(data["result"]["value"]))

    @classmethod
    async def _get_staked_total(cls, client: httpx.AsyncClient, address: str) -> Decimal:
        accounts: dict[str, Decimal] = {}
        for offset in (12, 44):
            try:
                data = await cls._rpc_call(
                    client,
                    "getProgramAccounts",
                    [
                        _STAKE_PROGRAM,
                        {
                            "encoding": "jsonParsed",
                            "filters": [{"memcmp": {"offset": offset, "bytes": address}}],
                        },
                    ],
                )
            except Exception as exc:
                logger.debug("Solana stake offset %d hata: %s", offset, exc)
                continue
            for acc in data.get("result", []) or []:
                pubkey = acc.get("pubkey")
                if pubkey and pubkey not in accounts:
                    lamports = Decimal(str(acc["account"]["lamports"]))
                    accounts[pubkey] = lamports
        return sum(accounts.values(), Decimal(0))

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await self._get_balance(client, self.address)
            return True
        except Exception:
            return False
