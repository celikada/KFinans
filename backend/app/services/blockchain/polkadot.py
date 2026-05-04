"""Polkadot cüzdan bakiye servisi.

DOT bakiyesi hem Polkadot Relay Chain'de hem Asset Hub parachain'de tutulabilir.
2024+ ekosisteminde spot DOT giderek Asset Hub'a taşındı (transferable balance
oradadır), staking ise Relay Chain'de kaldı. Servis ikisini paralel sorgulayıp
toplar.

substrate-interface kütüphanesi kullanılır — Substrate JSON-RPC üzerinden
state query (System.Account) yapar, anahtar gerektirmez.

Cache + single-flight (Bitcoin/Solana pattern'i) — substrate WS bağlantıları
yavaş kurulur, dashboard yenilemeleri tek seferlik çalışsın.
"""
import asyncio
import logging
import time
from decimal import Decimal

from substrateinterface import SubstrateInterface

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

PLANCK_PER_DOT = Decimal("10000000000")  # 10^10
_RELAY_RPC = "wss://polkadot-rpc.publicnode.com"
_ASSET_HUB_RPC = "wss://polkadot-asset-hub-rpc.polkadot.io"

# Cache: address → (timestamp, (relay_free, relay_reserved, hub_free))
_BALANCE_CACHE: dict[str, tuple[float, tuple[Decimal, Decimal, Decimal]]] = {}
_CACHE_TTL_SEC = 600  # 10 dk
_cache_lock = asyncio.Lock()
_INFLIGHT: dict[str, asyncio.Future] = {}


class PolkadotService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        try:
            relay_free, relay_reserved, hub_free = await self._cached_balance()
        except Exception as exc:
            logger.warning("Polkadot bakiye alınamadı [%s]: %s", self.address[:16], exc)
            return []

        liquid = ((relay_free + hub_free) / PLANCK_PER_DOT).quantize(Decimal("0.0001"))
        staked = (relay_reserved / PLANCK_PER_DOT).quantize(Decimal("0.0001"))

        if liquid <= 0 and staked <= 0:
            return []

        return [
            AssetData(
                symbol="DOT",
                name="Polkadot",
                provider="polkadot",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=liquid,
                staked_quantity=staked,
                wallet_address_id=self.wallet_address_id,
            )
        ]

    async def _cached_balance(self) -> tuple[Decimal, Decimal, Decimal]:
        loop = asyncio.get_running_loop()
        is_owner = False
        async with _cache_lock:
            cached = _BALANCE_CACHE.get(self.address)
            if cached and time.monotonic() - cached[0] < _CACHE_TTL_SEC:
                return cached[1]
            inflight = _INFLIGHT.get(self.address)
            if inflight is None:
                inflight = loop.create_future()
                _INFLIGHT[self.address] = inflight
                is_owner = True

        if not is_owner:
            return await inflight

        try:
            # substrate-interface async değil — thread pool'a delege et
            relay = await asyncio.to_thread(self._sync_query, _RELAY_RPC)
            hub = await asyncio.to_thread(self._sync_query, _ASSET_HUB_RPC)
            result = (relay[0], relay[1], hub[0])  # relay_free, relay_reserved, hub_free
            async with _cache_lock:
                _BALANCE_CACHE[self.address] = (time.monotonic(), result)
                _INFLIGHT.pop(self.address, None)
            inflight.set_result(result)
            return result
        except Exception as exc:
            async with _cache_lock:
                _INFLIGHT.pop(self.address, None)
            inflight.set_exception(exc)
            raise

    def _sync_query(self, rpc_url: str) -> tuple[Decimal, Decimal]:
        """Bir Substrate node'dan System.Account.data sorgular.
        Dönüş: (free, reserved) Planck cinsinden Decimal.
        """
        try:
            substrate = SubstrateInterface(url=rpc_url)
            result = substrate.query("System", "Account", [self.address])
            data = result.value.get("data", {})
            free = Decimal(str(data.get("free", 0)))
            reserved = Decimal(str(data.get("reserved", 0)))
            return free, reserved
        except Exception as exc:
            logger.warning("Polkadot RPC %s sorgusu fail: %s", rpc_url, exc)
            return Decimal(0), Decimal(0)

    async def health_check(self) -> bool:
        try:
            await asyncio.to_thread(self._sync_query, _RELAY_RPC)
            return True
        except Exception:
            return False
