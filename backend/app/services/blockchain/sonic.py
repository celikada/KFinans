from decimal import Decimal
from web3 import AsyncWeb3
from app.services.base import BaseBlockchainIntegration, AssetData
from app.config import settings

# Sonic SFC (Special Fee Contract) — staking arayüzü
# Adres Sonic dokümantasyonundan doğrulanmalı: https://docs.soniclabs.com
SFC_ADDRESS = "0xFC00FACE00000000000000000000000000000000"

# Minimum ABI: stake okuma için gerekli metodlar
SFC_ABI = [
    {
        "inputs": [{"name": "delegator", "type": "address"}, {"name": "toValidatorID", "type": "uint256"}],
        "name": "getStake",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "delegator", "type": "address"}, {"name": "toValidatorID", "type": "uint256"}],
        "name": "pendingRewards",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "lastValidatorID",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

WEI = Decimal("1e18")


class SonicService(BaseBlockchainIntegration):

    def __init__(self, address: str, wallet_address_id: str | None = None):
        super().__init__(address, wallet_address_id)
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.sonic_rpc_url))

    async def fetch(self) -> list[AssetData]:
        checksum_addr = AsyncWeb3.to_checksum_address(self.address)
        sfc = self._w3.eth.contract(address=AsyncWeb3.to_checksum_address(SFC_ADDRESS), abi=SFC_ABI)

        # Liquid S bakiyesi
        balance_wei = await self._w3.eth.get_balance(checksum_addr)
        liquid = Decimal(balance_wei) / WEI

        # Tüm validator'lara karşı stake miktarlarını sorgula
        total_staked = Decimal(0)
        total_rewards = Decimal(0)

        last_validator_id = await sfc.functions.lastValidatorID().call()
        for validator_id in range(1, last_validator_id + 1):
            try:
                stake_wei = await sfc.functions.getStake(checksum_addr, validator_id).call()
                rewards_wei = await sfc.functions.pendingRewards(checksum_addr, validator_id).call()
                total_staked += Decimal(stake_wei) / WEI
                total_rewards += Decimal(rewards_wei) / WEI
            except Exception:
                continue

        assets = []
        if liquid > 0 or total_staked > 0:
            assets.append(AssetData(
                symbol="S",
                name="Sonic",
                provider="sonic",
                asset_type="staked_crypto" if total_staked > 0 else "crypto",
                source_type="blockchain",
                liquid_quantity=liquid,
                staked_quantity=total_staked,
                pending_rewards=total_rewards,
                wallet_address_id=self.wallet_address_id,
            ))
        return assets

    async def health_check(self) -> bool:
        try:
            await self._w3.eth.get_balance(AsyncWeb3.to_checksum_address(self.address))
            return True
        except Exception:
            return False
