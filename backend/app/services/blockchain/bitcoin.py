"""Bitcoin cüzdan bakiye servisi (Esplora API + xpub HD desteği).

Tek adres veya xpub/ypub/zpub kabul eder:
- Tek adres: Esplora `/api/address/{addr}` sorgulanır (blockstream.info primary;
  mempool.space Oracle datacenter IP'sini blokladığından fallback host'lar var).
- Extended public key (xpub/ypub/zpub): BIP-44 (Legacy) ve BIP-84 (SegWit)
  derivation chain'leri (0=receive, 1=change) gap_limit=20 ile taranır,
  her bulunan adresin bakiyesi toplanır.

Ledger Live "Bitcoin 1 (Native SegWit)" hesabı için xpub formatında
export edilmiş anahtar BIP-84 path'inde olur; bu yüzden hem 44 hem 84
chain'i taranır ve gerçek bakiye veren chain otomatik bulunur.
"""

import asyncio
import logging
from decimal import Decimal

import httpx
from bip_utils import (
    Bip32Secp256k1,
    P2PKHAddrEncoder,
    P2WPKHAddrEncoder,
)

from app.core.cache import AsyncTTLCache
from app.services.base import AssetData, BaseBlockchainIntegration
from app.services.concurrency import gather_bounded

logger = logging.getLogger(__name__)

SATOSHI_PER_BTC = Decimal("100000000")
# Esplora API host'ları (aynı /api/address/{addr} + chain_stats şeması). KRİTİK:
# mempool.space Oracle Cloud datacenter IP'sini SYN-drop ediyor (Cloudflare;
# prod'dan TCP connect kurulamıyor → BTC scan 0 istek + timeout). blockstream.info
# Oracle'dan erişilebilir → primary. Sırayla denenir (ilk erişilebilen kullanılır).
_ESPLORA_HOSTS = (
    "https://blockstream.info/api/address/{addr}",
    "https://mempool.emzy.de/api/address/{addr}",
    "https://mempool.space/api/address/{addr}",
)


async def _esplora_get(client: httpx.AsyncClient, addr: str) -> dict:
    """Adres bilgisini Esplora host'larından çeker (sırayla, ilk erişilebilen).

    429 → tek retry. Tüm host'lar patlarsa son exception fırlatılır.
    """
    last_exc: Exception | None = None
    for host in _ESPLORA_HOSTS:
        try:
            resp = await client.get(host.format(addr=addr))
            if resp.status_code == 429:
                await asyncio.sleep(2.0)
                resp = await client.get(host.format(addr=addr))
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            continue
    raise last_exc if last_exc else RuntimeError("Esplora host yok")


_XPUB_PREFIXES = ("xpub", "ypub", "zpub", "Xpub", "Ypub", "Zpub")
_GAP_LIMIT = 20  # BIP-44 standardı: 20 ardışık boş adres → chain biter
# xpub adres taraması bounded-parallel: bir pencerede _GAP_LIMIT adres en fazla
# _SCAN_CONCURRENCY eşzamanlı sorgulanır (mempool.space rate-limit dengesi). Eski
# sıralı tarama (adres-adres + 0.3s sleep) yüzlerce adreste 45s'yi aşıyordu.
_SCAN_CONCURRENCY = 5

# In-memory cache + single-flight: xpub/adres → btc_balance, 30 dk TTL.
# Dashboard mempool.space rate limit'ine takılmasın diye; paralel cache miss
# çağrıları tek tarama paylaşır. TTL 30 dk: BTC bakiyesi sık değişmez, yavaş
# taramanın her 10 dk'da tekrarlanmasını önler (ilk başarılı tarama sonrası cache).
_balance_cache: AsyncTTLCache[Decimal] = AsyncTTLCache(ttl_sec=1800)


class BitcoinService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        try:
            btc_balance = await self._cached_balance()
        except Exception as exc:
            logger.warning("Bitcoin bakiye alınamadı [%s]: %s", self.address[:16], exc)
            return []

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

    async def _cached_balance(self) -> Decimal:
        async def _fetch() -> Decimal:
            if self.address.startswith(_XPUB_PREFIXES):
                return await self._fetch_xpub_balance(self.address)
            return await self._fetch_single_balance(self.address)

        return await _balance_cache.get_or_compute(self.address, _fetch)

    async def _fetch_single_balance(self, addr: str) -> Decimal:
        async with httpx.AsyncClient(timeout=15) as client:
            data = await _esplora_get(client, addr)
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

    @staticmethod
    async def _query_address(client: httpx.AsyncClient, addr: str) -> tuple[int, Decimal]:
        """Tek adresi Esplora'dan sorgular → (tx_count, pozitif_bakiye_sat).

        Host fallback (_esplora_get) içinde. Hata → (0, 0): adres gap-limit/bakiye
        açısından boş sayılır (orijinal sıralı tarama da böyle yapardı).
        """
        try:
            data = await _esplora_get(client, addr)
        except Exception as exc:
            logger.debug("xpub adres %s sorgulanamadı: %s", addr, exc)
            return 0, Decimal(0)
        cs = data.get("chain_stats", {})
        tx_count = cs.get("tx_count", 0)
        bal = Decimal(str(cs.get("funded_txo_sum", 0))) - Decimal(str(cs.get("spent_txo_sum", 0)))
        return tx_count, (bal if bal > 0 else Decimal(0))

    async def _scan_chain(
        self,
        node: Bip32Secp256k1,
        change: int,
        segwit: bool,
        client: httpx.AsyncClient,
    ) -> tuple[Decimal, bool]:
        """Bir chain'i (receive veya change) gap_limit'e kadar BOUNDED-PARALLEL tarar.

        Pencere = _GAP_LIMIT adres; her pencere en fazla _SCAN_CONCURRENCY eşzamanlı
        sorgulanır (mempool rate-limit dengesi). Sonuçlar SIRAYLA işlenir → gap-limit
        (20 ardışık boş) semantiği korunur. Eski adres-adres sıralı tarama (+0.3s sleep)
        yüzlerce adreste 45 sn'yi aşıyordu.

        Dönüş: (chain_sat, had_any_tx) — had_any_tx SegWit aktifse Legacy'yi atlamak için.
        """
        chain_sat = Decimal(0)
        had_any_tx = False
        consecutive_empty = 0
        idx = 0
        while consecutive_empty < _GAP_LIMIT and idx < 100:
            window = range(idx, min(idx + _GAP_LIMIT, 100))
            addrs = [self._derive_address(node, change, i, segwit) for i in window]
            results = await gather_bounded(
                addrs,
                lambda a: self._query_address(client, a),
                limit=_SCAN_CONCURRENCY,
            )
            for tx_count, bal in results:  # sıra korunur → gap-limit doğru
                if tx_count == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0
                    had_any_tx = True
                    chain_sat += bal
                if consecutive_empty >= _GAP_LIMIT:
                    break
            idx += len(addrs)
        return chain_sat, had_any_tx

    async def health_check(self) -> bool:
        try:
            if self.address.startswith(_XPUB_PREFIXES):
                Bip32Secp256k1.FromExtendedKey(self.address)
                return True
            async with httpx.AsyncClient(timeout=10) as client:
                await _esplora_get(client, self.address)
            return True
        except Exception:
            return False
