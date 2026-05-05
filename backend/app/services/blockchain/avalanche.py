import asyncio
import logging
from decimal import Decimal
import httpx
from web3 import AsyncWeb3
from app.services.base import BaseBlockchainIntegration, AssetData
from app.services.blockchain.evm_tokens import AVALANCHE_C_TOKENS, fetch_token_balances
from app.config import settings

logger = logging.getLogger(__name__)

NAVAX = Decimal("1e9")
WEI = Decimal("1e18")


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
        p_addr = f"P-{self.address}" if not self.address.startswith("P-") else self.address
        async with httpx.AsyncClient(timeout=15) as client:
            balance_resp, stake_resp = await asyncio.gather(
                client.post(settings.avalanche_p_api_url, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "platform.getBalance",
                    "params": {"addresses": [p_addr]},
                }),
                client.post(settings.avalanche_p_api_url, json={
                    "jsonrpc": "2.0", "id": 2,
                    "method": "platform.getStake",
                    "params": {"addresses": [p_addr], "encoding": "hex"},
                }),
                return_exceptions=False,
            )
            balance_resp.raise_for_status()
            stake_resp.raise_for_status()
            balance_data = balance_resp.json().get("result", {})
            stake_data = stake_resp.json().get("result", {})

        # getBalance — yeni API: unlockeds/lockedStakeables (assetID→amount mapping)
        # eski API: unlocked/lockedStakeable (tekil değer). İkisini de destekle.
        unlocked = self._sum_assets(balance_data.get("unlockeds")) \
            or self._to_decimal_navax(balance_data.get("unlocked"))
        locked_stakeable = self._sum_assets(balance_data.get("lockedStakeables")) \
            or self._to_decimal_navax(balance_data.get("lockedStakeable"))
        # Aktif validator stake (delegasyon dahil)
        staked = self._to_decimal_navax(stake_data.get("staked", 0))
        # Yeni API'de stakedOutputs varsa onun toplamı tercih edilir
        if "stakedOutputs" in stake_data and isinstance(stake_data["stakedOutputs"], list):
            # Bazı sürümler mapping yerine UTXO listesi döner — staked alanı bizde yeterli
            pass

        # Liquid = unlocked; Staked = aktif stake; lockedStakeable kategorize edilemediği
        # için staked'a dahil ediyoruz (kullanıcı için "kilitli ve stake'lenebilir" =
        # zaten tutuluyor demek).
        liquid = unlocked
        total_staked = staked + locked_stakeable

        assets = []
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
