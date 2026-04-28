from decimal import Decimal
from web3 import AsyncWeb3
from app.services.base import BaseBlockchainIntegration, AssetData
from app.config import settings

WEI = Decimal("1e18")


class EthereumService(BaseBlockchainIntegration):

    def __init__(self, address: str, wallet_address_id: str | None = None):
        super().__init__(address, wallet_address_id)
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.ethereum_rpc_url))

    async def fetch(self) -> list[AssetData]:
        checksum = AsyncWeb3.to_checksum_address(self.address)
        balance_wei = await self._w3.eth.get_balance(checksum)
        eth_balance = Decimal(balance_wei) / WEI

        assets = []
        if eth_balance > 0:
            assets.append(AssetData(
                symbol="ETH",
                name="Ethereum",
                provider="ethereum",
                asset_type="crypto",
                source_type="blockchain",
                liquid_quantity=eth_balance,
                wallet_address_id=self.wallet_address_id,
            ))
        # TODO: ERC-20 token bakiyeleri (Etherscan API veya token listesi ile)
        return assets

    async def health_check(self) -> bool:
        try:
            await self._w3.eth.get_balance(AsyncWeb3.to_checksum_address(self.address))
            return True
        except Exception:
            return False
