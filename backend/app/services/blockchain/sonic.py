import asyncio
import logging
from decimal import Decimal

from web3 import AsyncWeb3

from app.config import settings
from app.services.base import AssetData, BaseBlockchainIntegration
from app.services.blockchain._web3_utils import provider_request_kwargs

logger = logging.getLogger(__name__)

SFC_ADDRESS = "0xFC00FACE00000000000000000000000000000000"

SFC_ABI = [
    {
        "inputs": [
            {"name": "delegator", "type": "address"},
            {"name": "toValidatorID", "type": "uint256"},
        ],
        "name": "getStake",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "delegator", "type": "address"},
            {"name": "toValidatorID", "type": "uint256"},
        ],
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
_CONCURRENCY = 20  # paralel RPC çağrısı limiti


class SonicService(BaseBlockchainIntegration):
    def __init__(self, address: str, wallet_address_id: str | None = None):
        super().__init__(address, wallet_address_id)
        # Timeout'lu provider — ölü RPC fetch'i kilitlemesin (modül-local
        # AsyncWeb3 → testlerin monkeypatch'i çalışır).
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.sonic_rpc_url, request_kwargs=provider_request_kwargs()))

    async def fetch(self) -> list[AssetData]:
        checksum_addr = AsyncWeb3.to_checksum_address(self.address)
        sfc = self._w3.eth.contract(address=AsyncWeb3.to_checksum_address(SFC_ADDRESS), abi=SFC_ABI)

        balance_wei, last_validator_id = await asyncio.gather(
            self._w3.eth.get_balance(checksum_addr),
            sfc.functions.lastValidatorID().call(),
        )
        liquid = Decimal(balance_wei) / WEI

        # Paralel stake sorgusu — semaphore ile aşırı yükü önle
        sem = asyncio.Semaphore(_CONCURRENCY)

        async def query_validator(vid: int) -> tuple[int, int]:
            async with sem:
                try:
                    stake = await sfc.functions.getStake(checksum_addr, vid).call()
                    if stake == 0:
                        return 0, 0
                    rewards = await sfc.functions.pendingRewards(checksum_addr, vid).call()
                    return stake, rewards
                except Exception:
                    return 0, 0

        results = await asyncio.gather(*[query_validator(vid) for vid in range(1, last_validator_id + 1)])

        total_staked = sum(Decimal(s) for s, _ in results) / WEI
        total_rewards = sum(Decimal(r) for _, r in results) / WEI

        assets = []
        if liquid > 0 or total_staked > 0:
            assets.append(
                AssetData(
                    symbol="S",
                    name="Sonic",
                    provider="sonic",
                    asset_type="staked_crypto" if total_staked > 0 else "crypto",
                    source_type="blockchain",
                    liquid_quantity=liquid,
                    staked_quantity=total_staked,
                    pending_rewards=total_rewards,
                    wallet_address_id=self.wallet_address_id,
                )
            )
        return assets

    async def health_check(self) -> bool:
        try:
            await self._w3.eth.get_balance(AsyncWeb3.to_checksum_address(self.address))
            return True
        except Exception:
            return False
