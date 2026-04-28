from decimal import Decimal
import httpx
from web3 import AsyncWeb3
from app.services.base import BaseBlockchainIntegration, AssetData
from app.config import settings

NAVAX = Decimal("1e9")  # Avalanche nAVAX → AVAX
WEI = Decimal("1e18")


class AvalancheService(BaseBlockchainIntegration):
    """
    Avalanche P-Chain staking + C-Chain liquid AVAX.
    P-Chain adresi: P-avax1...
    C-Chain adresi: 0x... (EVM format)
    İki adres de aynı cüzdana ait olabilir ama format farklıdır.
    """

    def __init__(
        self,
        p_chain_address: str,
        c_chain_address: str,
        wallet_address_id: str | None = None,
    ):
        super().__init__(p_chain_address, wallet_address_id)
        self.p_chain_address = p_chain_address
        self.c_chain_address = c_chain_address
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.avalanche_c_rpc_url))

    async def _fetch_p_chain_stake(self) -> tuple[Decimal, Decimal]:
        """platform.getStake ile staked AVAX miktarını döner (staked, unlocked)."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.avalanche_p_api_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "platform.getStake",
                    "params": {"addresses": [self.p_chain_address], "encoding": "hex"},
                    "id": 1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            staked_navax = int(data["result"].get("staked", "0"), 16)
            return Decimal(staked_navax) / NAVAX, Decimal(0)

    async def fetch(self) -> list[AssetData]:
        staked_avax, pending = await self._fetch_p_chain_stake()

        # C-Chain liquid AVAX
        checksum = AsyncWeb3.to_checksum_address(self.c_chain_address)
        balance_wei = await self._w3.eth.get_balance(checksum)
        liquid_avax = Decimal(balance_wei) / WEI

        assets = []
        if liquid_avax > 0 or staked_avax > 0:
            assets.append(AssetData(
                symbol="AVAX",
                name="Avalanche",
                provider="avalanche",
                asset_type="staked_crypto" if staked_avax > 0 else "crypto",
                source_type="blockchain",
                liquid_quantity=liquid_avax,
                staked_quantity=staked_avax,
                pending_rewards=pending,
                wallet_address_id=self.wallet_address_id,
            ))
        return assets

    async def health_check(self) -> bool:
        try:
            await self._w3.eth.get_balance(AsyncWeb3.to_checksum_address(self.c_chain_address))
            return True
        except Exception:
            return False
