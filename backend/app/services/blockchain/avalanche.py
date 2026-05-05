import asyncio
import logging
import time
from decimal import Decimal
import httpx
from web3 import AsyncWeb3
from app.services.base import BaseBlockchainIntegration, AssetData
from app.services.blockchain.evm_tokens import AVALANCHE_C_TOKENS, fetch_token_balances
from app.config import settings

logger = logging.getLogger(__name__)

NAVAX = Decimal("1e9")
WEI = Decimal("1e18")

# Avalanche P-Chain public RPC ucu agresif rate-limit uygular (HTTP 429).
# Dashboard yenileme ve snapshot paralel cagrilari riski artirir.
# Cache + single-flight (Bitcoin pattern'i ile ayni) tutuyoruz.
_PCHAIN_CACHE: dict[str, tuple[float, dict]] = {}
_PCHAIN_CACHE_TTL_SEC = 600  # 10 dk
_pchain_cache_lock = asyncio.Lock()
_pchain_inflight: dict[str, asyncio.Future] = {}


class AvalanchePChainService(BaseBlockchainIntegration):
    """P-Chain bakiye + staking.

    `platform.getBalance` ile likit (unlocked) bakiye + `platform.getStake` ile
    aktif validator stake'i çekilir. Adres `P-` prefix'i ile gönderilmeli.
    """

    @staticmethod
    def _to_decimal_navax(raw) -> Decimal:
        """nAVAX (1e9) ham değerini Decimal'e çevirir. int veya '0x...' string olabilir."""
        if raw is None:
            return Decimal(0)
        if isinstance(raw, str):
            value = int(raw, 16) if raw.startswith("0x") else int(raw)
        else:
            value = int(raw)
        return Decimal(value) / NAVAX

    @classmethod
    def _sum_assets(cls, mapping) -> Decimal:
        """Yeni API: {assetID: amount} mapping → toplam (tek asset olduğu varsayılır,
        AVAX P-Chain üzerinde tek primary asset)."""
        if not isinstance(mapping, dict):
            return Decimal(0)
        total = Decimal(0)
        for v in mapping.values():
            total += cls._to_decimal_navax(v)
        return total

    async def fetch(self) -> list[AssetData]:
        try:
            data = await self._cached_fetch()
        except Exception as exc:
            logger.warning("Avalanche P-Chain bakiye alinamadi [%s]: %s", self.address[:16], exc)
            return []

        liquid = data["liquid"]
        total_staked = data["staked"]

        assets: list[AssetData] = []
        if liquid > 0 or total_staked > 0:
            assets.append(AssetData(
                symbol="AVAX",
                name="Avalanche",
                provider="avalanche_p",
                asset_type="staked_crypto" if total_staked > liquid else "crypto",
                source_type="blockchain",
                liquid_quantity=liquid,
                staked_quantity=total_staked,
                wallet_address_id=self.wallet_address_id,
            ))
        return assets

    async def _cached_fetch(self) -> dict:
        """Cache + single-flight (Bitcoin pattern). Public RPC 429 rate-limit'ini hafifletir."""
        loop = asyncio.get_running_loop()
        is_owner = False
        async with _pchain_cache_lock:
            cached = _PCHAIN_CACHE.get(self.address)
            if cached and time.monotonic() - cached[0] < _PCHAIN_CACHE_TTL_SEC:
                return cached[1]
            inflight = _pchain_inflight.get(self.address)
            if inflight is None:
                inflight = loop.create_future()
                _pchain_inflight[self.address] = inflight
                is_owner = True

        if not is_owner:
            return await inflight

        try:
            data = await self._fetch_balances()
            async with _pchain_cache_lock:
                _PCHAIN_CACHE[self.address] = (time.monotonic(), data)
                _pchain_inflight.pop(self.address, None)
            inflight.set_result(data)
            return data
        except Exception as exc:
            async with _pchain_cache_lock:
                _pchain_inflight.pop(self.address, None)
            inflight.set_exception(exc)
            raise

    async def _fetch_balances(self) -> dict:
        """Glacier (Routescan) REST API once denenir — public RPC 429 rate-limit'sizdir.
        Fail ederse JSON-RPC'ye fallback."""
        try:
            return await self._fetch_via_glacier()
        except Exception as exc:
            logger.warning("Glacier API basarisiz [%s], JSON-RPC'ye dusuyor: %s", self.address[:16], exc)
            return await self._fetch_via_rpc()

    async def _fetch_via_glacier(self) -> dict:
        """https://glacier-api.avax.network/v1/networks/mainnet/blockchains/p-chain/balances
        Yanit yapisi: {balances: {unlockedUnstaked, lockedStaked, lockedStakeable, pendingStaked, ...}}
        Her kategori list[{assetId, amount, denomination}] dondurur — biz AVAX (denomination=9) toplariz.
        """
        url = "https://glacier-api.avax.network/v1/networks/mainnet/blockchains/p-chain/balances"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params={"addresses": self.address})
            resp.raise_for_status()
            data = resp.json().get("balances", {})

        def _sum_avax(entries: list) -> Decimal:
            total = Decimal(0)
            for e in entries or []:
                if e.get("symbol") == "AVAX" or e.get("denomination") == 9:
                    total += self._to_decimal_navax(e.get("amount", "0"))
            return total

        liquid = _sum_avax(data.get("unlockedUnstaked"))
        # Aktif stake: lockedStaked + pendingStaked + unlockedStaked (delegasyon biten ama henuz claim'lenmemis)
        staked = (
            _sum_avax(data.get("lockedStaked"))
            + _sum_avax(data.get("pendingStaked"))
            + _sum_avax(data.get("unlockedStaked"))
            + _sum_avax(data.get("lockedStakeable"))
        )
        return {"liquid": liquid, "staked": staked}

    async def _fetch_via_rpc(self) -> dict:
        """JSON-RPC fallback: platform.getBalance + platform.getStake (sequential).
        429 alirsa 1s+2s backoff ile retry."""
        p_addr = f"P-{self.address}" if not self.address.startswith("P-") else self.address

        async def _rpc(client: httpx.AsyncClient, method: str, params: dict, req_id: int) -> dict:
            for attempt in range(3):
                resp = await client.post(settings.avalanche_p_api_url, json={
                    "jsonrpc": "2.0", "id": req_id, "method": method, "params": params,
                })
                if resp.status_code == 429 and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json().get("result", {}) or {}
            resp.raise_for_status()
            return {}

        async with httpx.AsyncClient(timeout=20) as client:
            balance_data = await _rpc(client, "platform.getBalance", {"addresses": [p_addr]}, 1)
            stake_data = await _rpc(client, "platform.getStake", {"addresses": [p_addr], "encoding": "hex"}, 2)

        unlocked = self._sum_assets(balance_data.get("unlockeds")) \
            or self._to_decimal_navax(balance_data.get("unlocked"))
        locked_stakeable = self._sum_assets(balance_data.get("lockedStakeables")) \
            or self._to_decimal_navax(balance_data.get("lockedStakeable"))
        staked = self._to_decimal_navax(stake_data.get("staked", 0))
        return {"liquid": unlocked, "staked": staked + locked_stakeable}

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    settings.avalanche_p_api_url,
                    json={"jsonrpc": "2.0", "method": "platform.getHeight", "params": {}, "id": 1},
                )
                return r.status_code == 200
        except Exception:
            return False


_AVAX_FALLBACK_RPCS = (
    "https://api.avax.network/ext/bc/C/rpc",
    "https://avalanche.public-rpc.com",
    "https://avalanche.drpc.org",
    "https://1rpc.io/avax/c",
)


class AvalancheCChainService(BaseBlockchainIntegration):
    """C-Chain liquid AVAX (EVM) + ERC-20 tokens."""

    async def fetch(self) -> list[AssetData]:
        checksum = AsyncWeb3.to_checksum_address(self.address)
        balance_wei = None
        for rpc in (settings.avalanche_c_rpc_url, *_AVAX_FALLBACK_RPCS):
            if not rpc:
                continue
            try:
                w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc))
                balance_wei = await w3.eth.get_balance(checksum)
                self._w3 = w3
                break
            except Exception as exc:
                logger.warning("AVAX C RPC %s başarısız: %s", rpc[:40], exc)

        if balance_wei is None:
            logger.error("Tüm AVAX C RPC'leri başarısız [%s]", self.address[:12])
            return []

        liquid = Decimal(balance_wei) / WEI

        assets = []
        if liquid > 0:
            assets.append(AssetData(
                symbol="AVAX",
                name="Avalanche",
                provider="avalanche_c",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=liquid,
                wallet_address_id=self.wallet_address_id,
            ))

        # ERC-20 tokens (sAVAX, USDT.e, USDC.e)
        try:
            token_balances = await fetch_token_balances(self._w3, self.address, AVALANCHE_C_TOKENS)
            for token, amount in token_balances:
                assets.append(AssetData(
                    symbol=token.symbol, name=token.name,
                    provider="avalanche_c", asset_type="crypto", source_type="blockchain",
                    liquid_quantity=amount,
                    wallet_address_id=self.wallet_address_id,
                ))
        except Exception as exc:
            logger.warning("Avalanche C ERC-20 tarama hatası [%s]: %s", self.address[:12], exc)
        return assets

    async def health_check(self) -> bool:
        try:
            await self._w3.eth.get_balance(AsyncWeb3.to_checksum_address(self.address))
            return True
        except Exception:
            return False
