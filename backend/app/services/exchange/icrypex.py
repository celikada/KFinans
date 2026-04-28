import asyncio
import httpx
from decimal import Decimal
from app.services.base import BaseIntegration, AssetData

_TOKEN_URL = "https://account.icrypex.com/connect/token"
_BASE = "https://api.icrypex.com"
_SPOT_URL = f"{_BASE}/v1/wallet/spot"
_EARN_URL = f"{_BASE}/v1/user-earn"
_TICKERS_URL = f"{_BASE}/v1/tickers"
_CLIENT_ID = "coretech9"
_SCOPE = "openid profile email offline_access"
_EARN_INCLUDE = {"Earn", "Completed"}


class ICrypexService(BaseIntegration):
    """
    iCrypex entegrasyonu — OAuth2 ROPC (password grant).
    email → api_key, password → api_secret alanında saklanır.
    Spot + Earn (aktif/tamamlanmış) bakiyeleri birleştirilir.
    """

    def __init__(self, email: str, password: str):
        self._email = email
        self._password = password

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": _CLIENT_ID,
                "username": self._email,
                "password": self._password,
                "scope": _SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise ValueError(f"iCrypex oturum açılamadı (HTTP {resp.status_code}): {resp.text[:200]}")
        return resp.json()["access_token"]

    async def fetch(self) -> list[AssetData]:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await self._get_access_token(client)
            auth = {"Authorization": f"Bearer {token}", "x-client": "web"}

            spot_resp, earn_resp, ticker_resp = await asyncio.gather(
                client.get(_SPOT_URL, headers=auth),
                client.get(_EARN_URL, headers=auth),
                client.get(_TICKERS_URL),
            )
            spot_resp.raise_for_status()
            ticker_resp.raise_for_status()

        tickers = {t["symbol"]: t for t in ticker_resp.json()}

        # Spot bakiyeler: symbol -> {liquid, staked}
        balances: dict[str, dict] = {}
        spot_data = spot_resp.json()
        spot_items = spot_data if isinstance(spot_data, list) else spot_data.get("content", [])
        for item in spot_items:
            symbol = str(item.get("asset", "")).strip().upper()
            total = Decimal(str(item.get("total", 0) or 0))
            available = Decimal(str(item.get("available", total) or total))
            if not symbol or total <= 0:
                continue
            balances[symbol] = {"liquid": available, "staked": total - available}

        # Earn bakiyeler: anapara + birikmiş faiz → staked_quantity
        if earn_resp.status_code == 200:
            for item in earn_resp.json():
                if item.get("status") not in _EARN_INCLUDE:
                    continue
                symbol = str(item.get("assetSymbol", "")).strip().upper()
                principal = Decimal(str(item.get("quantity", 0) or 0))
                reward = Decimal(str(item.get("rewardQuantity", 0) or 0))
                locked = principal + reward
                if not symbol or locked <= 0:
                    continue
                if symbol in balances:
                    balances[symbol]["staked"] += locked
                else:
                    balances[symbol] = {"liquid": Decimal(0), "staked": locked}

        assets = []
        for symbol, bal in balances.items():
            ticker_key = f"{symbol}USDT"
            price_usd = Decimal(0)
            if ticker_key in tickers:
                price_usd = Decimal(str(tickers[ticker_key].get("last", 0) or 0))

            assets.append(AssetData(
                symbol=symbol,
                name=symbol,
                provider="icrypex",
                asset_type="crypto",
                source_type="exchange",
                liquid_quantity=bal["liquid"],
                staked_quantity=bal["staked"],
                unit_price_usd=price_usd,
            ))
        return assets

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                token = await self._get_access_token(client)
                r = await client.get(_SPOT_URL, headers={"Authorization": f"Bearer {token}"})
                return r.status_code == 200
        except Exception:
            return False


