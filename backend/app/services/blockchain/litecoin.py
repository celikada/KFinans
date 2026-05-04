"""Litecoin cüzdan bakiye servisi.

Bitcoin pattern'inin Litecoin uyarlaması:
- Tek adres (ltc1.../1.../3...): doğrudan litecoinspace.org `/api/address/{addr}`
- Ltub xpub: BIP-84 SegWit chain'leri (0=receive, 1=change) gap_limit=20 ile tarama

Ltub Litecoin BIP-32 prefix'i (`019da462`) bip_utils tarafından kabul edilmediği
için Bitcoin xpub prefix'ine (`0488B21E`) version-byte swap yapılır — anahtar
matematiği aynı, sadece serialization formatı standart Bitcoin xpub'a benzer.
Sonra P2WPKHAddrEncoder ile `hrp='ltc'` kullanılarak Litecoin Native SegWit
(ltc1q...) adresleri türetilir.

Cache + single-flight pattern Bitcoin servisinden kopyalandı.
"""
import asyncio
import logging
import time
from decimal import Decimal

import base58
import httpx
from bip_utils import (
    Bip32Secp256k1,
    P2WPKHAddrEncoder,
)

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

LITOSHI_PER_LTC = Decimal("100000000")
_LTCSPACE_API = "https://litecoinspace.org/api/address/{addr}"
_LTUB_PREFIX = bytes.fromhex("019da462")
_XPUB_PREFIX = bytes.fromhex("0488B21E")
_GAP_LIMIT = 20

_BALANCE_CACHE: dict[str, tuple[float, Decimal]] = {}
_CACHE_TTL_SEC = 600
_cache_lock = asyncio.Lock()
_INFLIGHT: dict[str, asyncio.Future] = {}


def _looks_like_xpub(addr: str) -> bool:
    return addr.startswith(("Ltub", "Ltpv", "xpub", "ypub", "zpub"))


def _ltub_to_xpub(ltub: str) -> str:
    """Litecoin Ltub'u Bitcoin xpub prefix'iyle yeniden serialize eder.
    Anahtar matematiği aynı; bip_utils standart xpub gibi parse eder."""
    raw = base58.b58decode_check(ltub)
    if not (raw.startswith(_LTUB_PREFIX) or raw.startswith(_XPUB_PREFIX)):
        raise ValueError("Geçersiz Litecoin xpub formatı")
    new_raw = _XPUB_PREFIX + raw[4:]
    return base58.b58encode_check(new_raw).decode()


class LitecoinService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        try:
            ltc_balance = await self._cached_balance()
        except Exception as exc:
            logger.warning("Litecoin bakiye alınamadı [%s]: %s", self.address[:16], exc)
            return []

        if ltc_balance <= 0:
            return []

        return [
            AssetData(
                symbol="LTC",
                name="Litecoin",
                provider="litecoin",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=ltc_balance.quantize(Decimal("0.00000001")),
                wallet_address_id=self.wallet_address_id,
            )
        ]

    async def _cached_balance(self) -> Decimal:
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
            if _looks_like_xpub(self.address):
                bal = await self._fetch_xpub_balance(self.address)
            else:
                bal = await self._fetch_single_balance(self.address)
            async with _cache_lock:
                _BALANCE_CACHE[self.address] = (time.monotonic(), bal)
                _INFLIGHT.pop(self.address, None)
            inflight.set_result(bal)
            return bal
        except Exception as exc:
            async with _cache_lock:
                _INFLIGHT.pop(self.address, None)
            inflight.set_exception(exc)
            raise

    async def _fetch_single_balance(self, addr: str) -> Decimal:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_LTCSPACE_API.format(addr=addr))
            resp.raise_for_status()
            data = resp.json()
        cs = data.get("chain_stats", {})
        balance_sat = Decimal(str(cs.get("funded_txo_sum", 0))) - Decimal(str(cs.get("spent_txo_sum", 0)))
        return balance_sat / LITOSHI_PER_LTC

    async def _fetch_xpub_balance(self, xpub: str) -> Decimal:
        try:
            xpub_canonical = _ltub_to_xpub(xpub) if xpub.startswith(("Ltub", "Ltpv")) else xpub
            node = Bip32Secp256k1.FromExtendedKey(xpub_canonical)
        except Exception as exc:
            raise ValueError(f"Geçersiz Litecoin xpub: {exc}") from exc

        total_sat = Decimal(0)
        async with httpx.AsyncClient(timeout=20) as client:
            for change in (0, 1):
                chain_sat, _ = await self._scan_chain(node, change, client)
                total_sat += chain_sat
        return total_sat / LITOSHI_PER_LTC

    @staticmethod
    def _derive_address(node: Bip32Secp256k1, change: int, idx: int) -> str:
        child = node.DerivePath(f"{change}/{idx}")
        pub_bytes = child.PublicKey().RawCompressed().ToBytes()
        return P2WPKHAddrEncoder.EncodeKey(pub_bytes, hrp="ltc", net_ver=b"")

    async def _scan_chain(
        self, node: Bip32Secp256k1, change: int, client: httpx.AsyncClient,
    ) -> tuple[Decimal, bool]:
        empty_streak = 0
        idx = 0
        chain_sat = Decimal(0)
        had_any_tx = False
        while empty_streak < _GAP_LIMIT and idx < 100:
            addr = self._derive_address(node, change, idx)
            try:
                resp = await client.get(_LTCSPACE_API.format(addr=addr))
                if resp.status_code == 429:
                    await asyncio.sleep(2.0)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.debug("LTC adres %s sorgulanamadı: %s", addr, exc)
                empty_streak += 1
                idx += 1
                await asyncio.sleep(0.5)
                continue
            cs = data.get("chain_stats", {})
            tx_count = cs.get("tx_count", 0)
            if tx_count == 0:
                empty_streak += 1
            else:
                empty_streak = 0
                had_any_tx = True
                bal = Decimal(str(cs.get("funded_txo_sum", 0))) - Decimal(str(cs.get("spent_txo_sum", 0)))
                if bal > 0:
                    chain_sat += bal
            idx += 1
            await asyncio.sleep(0.3)
        return chain_sat, had_any_tx

    async def health_check(self) -> bool:
        try:
            if _looks_like_xpub(self.address):
                if self.address.startswith(("Ltub", "Ltpv")):
                    _ltub_to_xpub(self.address)
                return True
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(_LTCSPACE_API.format(addr=self.address))
                resp.raise_for_status()
            return True
        except Exception:
            return False
