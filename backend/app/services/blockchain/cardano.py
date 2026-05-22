"""Cardano cüzdan bakiye servisi (Koios public API).

Üç giriş formatını kabul eder:
- `stake1...` (en iyi) — bütün cüzdan toplamı + ödüller
- `addr1...` — Shelley base address; içinden stake credential türetilip
  stake1 oluşturulur, sonra account_info çağrılır (HD cüzdandaki tüm
  payment adreslerinin toplamı kapsanır)
- `addr_test1...` — testnet, şimdilik desteklenmiyor

Public Koios API anahtar gerektirmez. Endpoint:
- POST /api/v1/account_info {"_stake_addresses": ["stake1..."]}
  → { total_balance, rewards_available, ... }
"""

import logging
from decimal import Decimal

import httpx
from bip_utils import Bech32Decoder, Bech32Encoder

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

LOVELACE_PER_ADA = Decimal("1000000")  # 10^6
_KOIOS_URL = "https://api.koios.rest/api/v1/account_info"


def _addr_to_stake(addr: str) -> str:
    """Cardano Shelley base address (addr1...) içinden stake1 türetir.

    Address yapısı (57 byte):
      [header: 1B] [payment_hash: 28B] [stake_hash: 28B]
    Stake address yapısı:
      [header 0xE0|network: 1B] [stake_hash: 28B]
    """
    data = Bech32Decoder.Decode("addr", addr)
    if len(data) < 57:
        raise ValueError("Cardano addr1 formatı geçersiz (en az 57 byte gerekli)")
    network = data[0] & 0x0F
    stake_hash = data[29:57]
    stake_data = bytes([0xE0 | network]) + stake_hash
    return Bech32Encoder.Encode("stake", stake_data)


class CardanoService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        try:
            stake_addr = self._normalize_to_stake(self.address)
        except Exception as exc:
            logger.warning("Cardano adres çözümlenemedi [%s]: %s", self.address[:20], exc)
            return []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    _KOIOS_URL,
                    headers={"Content-Type": "application/json"},
                    json={"_stake_addresses": [stake_addr]},
                )
                resp.raise_for_status()
                rows = resp.json()
        except Exception as exc:
            logger.warning("Cardano Koios sorgusu başarısız: %s", exc)
            return []

        if not rows:
            return []

        info = rows[0]
        utxo = Decimal(str(info.get("utxo", 0)))  # likit
        rewards = Decimal(str(info.get("rewards_available", 0)))  # claim edilebilir ödül

        liquid_ada = (utxo / LOVELACE_PER_ADA).quantize(Decimal("0.000001"))
        rewards_ada = (rewards / LOVELACE_PER_ADA).quantize(Decimal("0.000001"))

        if liquid_ada <= 0 and rewards_ada <= 0:
            return []

        return [
            AssetData(
                symbol="ADA",
                name="Cardano",
                provider="cardano",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=liquid_ada,
                pending_rewards=rewards_ada,
                wallet_address_id=self.wallet_address_id,
            )
        ]

    @staticmethod
    def _normalize_to_stake(address: str) -> str:
        if address.startswith("stake1"):
            return address
        if address.startswith("addr1"):
            return _addr_to_stake(address)
        raise ValueError(f"Bilinmeyen Cardano adres prefix: {address[:8]}")

    async def health_check(self) -> bool:
        try:
            self._normalize_to_stake(self.address)
            return True
        except Exception:
            return False
