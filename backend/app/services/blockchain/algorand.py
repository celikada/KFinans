"""Algorand cüzdan bakiye servisi (Algonode public API)."""

import logging
from decimal import Decimal

import httpx

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

MICRO_ALGO = Decimal("1000000")  # 10^6
_ALGONODE_API = "https://mainnet-api.algonode.cloud/v2/accounts/{addr}"


class AlgorandService(BaseBlockchainIntegration):
    """Algorand bakiyesi (native ALGO). ASA token desteği şimdilik yok.

    Algonode public — API anahtarı gerektirmez, rate limit yumuşak.
    """

    async def fetch(self) -> list[AssetData]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_ALGONODE_API.format(addr=self.address))
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Algorand bakiye alınamadı [%s]: %s", self.address[:12], exc)
            return []

        amount = Decimal(str(data.get("amount", 0)))
        # rewards burada toplam ödül — already-claimed ödüller "amount"'a dahil,
        # "rewards" pending. Toplama ekleyelim.
        pending_rewards = Decimal(str(data.get("rewards", 0)))
        liquid_algo = (amount / MICRO_ALGO).quantize(Decimal("0.000001"))
        rewards_algo = (pending_rewards / MICRO_ALGO).quantize(Decimal("0.000001"))

        if liquid_algo <= 0 and rewards_algo <= 0:
            return []

        return [
            AssetData(
                symbol="ALGO",
                name="Algorand",
                provider="algorand",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=liquid_algo,
                pending_rewards=rewards_algo,
                wallet_address_id=self.wallet_address_id,
            )
        ]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(_ALGONODE_API.format(addr=self.address))
                resp.raise_for_status()
            return True
        except Exception:
            return False
