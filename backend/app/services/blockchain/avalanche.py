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
    """P-Chain staking: platform.getStake API."""

    async def fetch(self) -> list[AssetData]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.avalanche_p_api_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "platform.getStake",
                    "params": {"addresses": [self.address], "encoding": "hex"},
                    "id": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        staked_raw = result.get("staked", "0x0")
        staked_navax = int(staked_raw, 16) if isinstance(staked_raw, str) else int(staked_raw)
        staked_avax = Decimal(staked_navax) / NAVAX

        assets = []
        if staked_avax > 0:
            assets.append(AssetData(
                symbol="AVAX",
                name="Avalanche",
                provider="avalanche_p",
                asset_type="staked_crypto",
                source_type="blockchain",
                liquid_quantity=Decimal(0),
                staked_quantity=staked_avax,
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
