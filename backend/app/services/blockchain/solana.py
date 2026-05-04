"""Solana cüzdan bakiye servisi.

Native SOL bakiyesi + stake hesaplarındaki delegasyonu toplar.
- Native: `getBalance` RPC (lamports → SOL)
- Stake: `getProgramAccounts` ile kullanıcının withdrawer authority'siyle
  açılmış stake hesapları taranır, her birinin delegated stake'i toplanır.

Public RPC: api.mainnet-beta.solana.com (rate limit ~10 req/s).
"""
import logging
from decimal import Decimal

import httpx

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = Decimal("1000000000")  # 10^9
_RPC_URL = "https://api.mainnet-beta.solana.com"
_STAKE_PROGRAM = "Stake11111111111111111111111111111111111111"


class SolanaService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                native_lamports = await self._get_balance(client, self.address)
                staked_lamports = await self._get_staked_total(client, self.address)
        except Exception as exc:
            logger.warning("Solana bakiye alınamadı [%s]: %s", self.address[:16], exc)
            return []

        liquid_sol = (native_lamports / LAMPORTS_PER_SOL).quantize(Decimal("0.000000001"))
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

    @staticmethod
    async def _get_balance(client: httpx.AsyncClient, address: str) -> Decimal:
        resp = await client.post(_RPC_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address],
        })
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Solana RPC error: {data['error']}")
        return Decimal(str(data["result"]["value"]))

    @staticmethod
    async def _get_staked_total(client: httpx.AsyncClient, address: str) -> Decimal:
        """Adresin withdrawer/staker authority olduğu stake hesaplarını topla.

        getProgramAccounts iki memcmp filter ile çağırılır (offset 12 = staker,
        offset 44 = withdrawer). Native Ledger staking'de ikisi de aynı kullanıcı
        olur. Aşırı eşleşme durumunda set ile dedup yapılır.
        """
        accounts: dict[str, Decimal] = {}
        for offset in (12, 44):
            resp = await client.post(_RPC_URL, json={
                "jsonrpc": "2.0", "id": 1, "method": "getProgramAccounts",
                "params": [
                    _STAKE_PROGRAM,
                    {
                        "encoding": "jsonParsed",
                        "filters": [
                            {"memcmp": {"offset": offset, "bytes": address}},
                        ],
                    },
                ],
            })
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                logger.debug("Solana stake offset %d hata: %s", offset, data["error"])
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
