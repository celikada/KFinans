"""Bitcoin cüzdan bakiye servisi (mempool.space public API)."""
import logging
from decimal import Decimal

import httpx

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

SATOSHI_PER_BTC = Decimal("100000000")  # 10^8
_MEMPOOL_API = "https://mempool.space/api/address/{addr}"


class BitcoinService(BaseBlockchainIntegration):
    """Bitcoin adresinin onaylanmış bakiyesini mempool.space'ten çeker.

    Adres formatları desteklenir:
      - Legacy (P2PKH): 1...
      - SegWit P2SH: 3...
      - Native SegWit (Bech32): bc1q...
      - Taproot: bc1p...

    API anahtarı gerekmez. mempool.space rate limit yumuşak (~1 req/sn).
    """

    async def fetch(self) -> list[AssetData]:
        url = _MEMPOOL_API.format(addr=self.address)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Bitcoin bakiye alınamadı [%s]: %s", self.address[:12], exc)
            return []

        chain_stats = data.get("chain_stats", {})
        funded = Decimal(str(chain_stats.get("funded_txo_sum", 0)))
        spent = Decimal(str(chain_stats.get("spent_txo_sum", 0)))
        balance_sat = funded - spent
        if balance_sat <= 0:
            return []

        btc_balance = (balance_sat / SATOSHI_PER_BTC).quantize(Decimal("0.00000001"))
        return [
            AssetData(
                symbol="BTC",
                name="Bitcoin",
                provider="bitcoin",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=btc_balance,
                wallet_address_id=self.wallet_address_id,
            )
        ]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(_MEMPOOL_API.format(addr=self.address))
                resp.raise_for_status()
            return True
        except Exception:
            return False
