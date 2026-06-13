"""Ethereum cüzdan: native ETH + ERC-20 token bakiyeleri.

Birincil RPC `settings.ethereum_rpc_url`. Başarısız olursa public fallback
RPC'leri sırayla denenir. Bir RPC çalışınca o session ile devam edilir.
"""

import logging
from decimal import Decimal

from web3 import AsyncWeb3

from app.config import settings
from app.services.base import AssetData, BaseBlockchainIntegration
from app.services.blockchain._web3_utils import provider_request_kwargs, web3_with_fallback
from app.services.blockchain.evm_tokens import fetch_ethereum_tokens_via_ethplorer

logger = logging.getLogger(__name__)

WEI = Decimal("1e18")

# Birincil + fallback public RPC'ler. settings.ethereum_rpc_url öncelikli.
# NOT: eth.llamarpc.com (eski default) 521 döndürüyor — config default'u
# publicnode'a çevrildi; bu liste yedek olarak çalışan RPC'leri tutar.
_FALLBACK_RPCS = (
    "https://ethereum.publicnode.com",
    "https://eth.merkle.io",
    "https://1rpc.io/eth",
    "https://rpc.ankr.com/eth",
)


def _make_w3(rpc: str) -> AsyncWeb3:
    # Modül-local AsyncWeb3 ile kur (testlerin monkeypatch'i çalışsın) + timeout.
    return AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc, request_kwargs=provider_request_kwargs()))


class EthereumService(BaseBlockchainIntegration):
    async def fetch(self) -> list[AssetData]:
        # Çalışan RPC bul (native balance ile test ediyoruz) — her deneme
        # timeout + asyncio.wait_for ile bounded; ölü RPC fetch'i kilitlemez.
        checksum = AsyncWeb3.to_checksum_address(self.address)
        w3, balance_wei = await web3_with_fallback(
            _make_w3,
            (settings.ethereum_rpc_url, *_FALLBACK_RPCS),
            lambda c: c.eth.get_balance(checksum),
            label="ETH RPC",
        )
        if balance_wei is None:
            logger.error("Tüm ETH RPC'leri başarısız [%s]", self.address[:12])
            return []
        self._w3 = w3

        eth_balance = Decimal(balance_wei) / WEI
        assets: list[AssetData] = []
        if eth_balance > 0:
            assets.append(
                AssetData(
                    symbol="ETH",
                    name="Ethereum",
                    provider="ethereum",
                    asset_type="crypto",
                    source_type="blockchain",
                    liquid_quantity=eth_balance,
                    wallet_address_id=self.wallet_address_id,
                )
            )

        # ERC-20 tokens — Ethplorer (RPC'den bağımsız)
        try:
            for token, amount in await fetch_ethereum_tokens_via_ethplorer(self.address):
                assets.append(
                    AssetData(
                        symbol=token.symbol,
                        name=token.name,
                        provider="ethereum",
                        asset_type="crypto",
                        source_type="blockchain",
                        liquid_quantity=amount,
                        wallet_address_id=self.wallet_address_id,
                    )
                )
        except Exception as exc:
            logger.warning("Ethereum ERC-20 tarama hatası [%s]: %s", self.address[:12], exc)
        return assets

    async def health_check(self) -> bool:
        try:
            await self.fetch()
            return True
        except Exception:
            return False
