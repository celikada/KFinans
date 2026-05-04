"""Bitcoin cüzdan bakiye servisi (mempool.space + xpub HD desteği).

Tek adres veya xpub/ypub/zpub kabul eder:
- Tek adres: doğrudan mempool.space `/api/address/{addr}` sorgulanır.
- Extended public key (xpub/ypub/zpub): BIP-44 (Legacy) ve BIP-84 (SegWit)
  derivation chain'leri (0=receive, 1=change) gap_limit=20 ile taranır,
  her bulunan adresin bakiyesi toplanır.

Ledger Live "Bitcoin 1 (Native SegWit)" hesabı için xpub formatında
export edilmiş anahtar BIP-84 path'inde olur; bu yüzden hem 44 hem 84
chain'i taranır ve gerçek bakiye veren chain otomatik bulunur.
"""
import asyncio
import logging
import time
from decimal import Decimal

import httpx
from bip_utils import (
    Bip32Secp256k1,
    P2PKHAddrEncoder,
    P2WPKHAddrEncoder,
)

from app.services.base import AssetData, BaseBlockchainIntegration

logger = logging.getLogger(__name__)

SATOSHI_PER_BTC = Decimal("100000000")
_MEMPOOL_API = "https://mempool.space/api/address/{addr}"
_XPUB_PREFIXES = ("xpub", "ypub", "zpub", "Xpub", "Ypub", "Zpub")
_GAP_LIMIT = 20  # BIP-44 standardı: 20 ardışık boş adres → chain biter

# In-memory cache: xpub/adres → (timestamp, btc_balance)
# Dashboard her yenilendiğinde mempool.space rate limit'ine takılmasın diye.
# Snapshot servisi cache'i bypass etmez — her snapshot fresh fetch yapar.
_BALANCE_CACHE: dict[str, tuple[float, Decimal]] = {}
_CACHE_TTL_SEC = 600  # 10 dk
_cache_lock = asyncio.Lock()


class BitcoinService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        # Cache lookup: dashboard yenileme rate limit yememesin diye 10dk
        async with _cache_lock:
            cached = _BALANCE_CACHE.get(self.address)
            if cached and time.monotonic() - cached[0] < _CACHE_TTL_SEC:
                btc_balance = cached[1]
            else:
                cached = None

        if cached is None:
            try:
                if self.address.startswith(_XPUB_PREFIXES):
                    btc_balance = await self._fetch_xpub_balance(self.address)
                else:
                    btc_balance = await self._fetch_single_balance(self.address)
            except Exception as exc:
                logger.warning("Bitcoin bakiye alınamadı [%s]: %s", self.address[:16], exc)
                return []

            async with _cache_lock:
                _BALANCE_CACHE[self.address] = (time.monotonic(), btc_balance)

        if btc_balance <= 0:
            return []

        return [
            AssetData(
                symbol="BTC",
                name="Bitcoin",
                provider="bitcoin",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=btc_balance.quantize(Decimal("0.00000001")),
                wallet_address_id=self.wallet_address_id,
            )
        ]

    async def _fetch_single_balance(self, addr: str) -> Decimal:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_MEMPOOL_API.format(addr=addr))
            resp.raise_for_status()
            data = resp.json()
        cs = data.get("chain_stats", {})
        balance_sat = Decimal(str(cs.get("funded_txo_sum", 0))) - Decimal(str(cs.get("spent_txo_sum", 0)))
        return balance_sat / SATOSHI_PER_BTC

    async def _fetch_xpub_balance(self, xpub: str) -> Decimal:
        """xpub/ypub/zpub'tan türetilen aktif adreslerin toplam bakiyesi.

        Önce BIP-84 (Native SegWit, bc1q...) taranır — modern cüzdanlar
        (Ledger, Trezor, Sparrow) varsayılan olarak bunu kullanır.
        SegWit'te tx yoksa BIP-44 (Legacy, 1...) chain'i taranır.
        Her chain için receive (0) ve change (1) gap_limit=20 ile.
        """
        try:
            node = Bip32Secp256k1.FromExtendedKey(xpub)
        except Exception as exc:
            raise ValueError(f"Geçersiz xpub: {exc}") from exc

        total_sat = Decimal(0)
        async with httpx.AsyncClient(timeout=20) as client:
            # Önce SegWit
            segwit_active = False
            for change in (0, 1):
                chain_sat, had_tx = await self._scan_chain(node, change, True, client)
                total_sat += chain_sat
                if had_tx:
                    segwit_active = True

            # SegWit'te hiç işlem yoksa Legacy'yi de dene
            if not segwit_active:
                for change in (0, 1):
                    chain_sat, _ = await self._scan_chain(node, change, False, client)
                    total_sat += chain_sat

        return total_sat / SATOSHI_PER_BTC

    @staticmethod
    def _derive_address(node: Bip32Secp256k1, change: int, idx: int, segwit: bool) -> str:
        child = node.DerivePath(f"{change}/{idx}")
        pub_bytes = child.PublicKey().RawCompressed().ToBytes()
        if segwit:
            return P2WPKHAddrEncoder.EncodeKey(pub_bytes, hrp="bc", net_ver=b"")
        return P2PKHAddrEncoder.EncodeKey(pub_bytes, net_ver=b"\x00")

    async def _scan_chain(
        self,
        node: Bip32Secp256k1,
        change: int,
        segwit: bool,
        client: httpx.AsyncClient,
    ) -> tuple[Decimal, bool]:
        """Bir chain'i (receive veya change) gap_limit'e kadar tarar.

        Dönüş: (chain_sat, had_any_tx) — had_any_tx, hiç işlemli adres bulundu mu?
        Bu bilgi, SegWit'te aktivite varsa Legacy'yi atlamak için kullanılır.
        """
        empty_streak = 0
        idx = 0
        chain_sat = Decimal(0)
        had_any_tx = False
        while empty_streak < _GAP_LIMIT and idx < 100:
            addr = self._derive_address(node, change, idx, segwit)
            try:
                resp = await client.get(_MEMPOOL_API.format(addr=addr))
                if resp.status_code == 429:
                    # Rate limit — bekle ve aynı index'i tekrar dene
                    await asyncio.sleep(2.0)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.debug("xpub adres %s sorgulanamadı: %s", addr, exc)
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
            await asyncio.sleep(0.3)  # mempool.space rate limit yumuşak ~1 req/s
        return chain_sat, had_any_tx

    async def health_check(self) -> bool:
        try:
            if self.address.startswith(_XPUB_PREFIXES):
                Bip32Secp256k1.FromExtendedKey(self.address)
                return True
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(_MEMPOOL_API.format(addr=self.address))
                resp.raise_for_status()
            return True
        except Exception:
            return False
