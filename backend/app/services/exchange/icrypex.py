import httpx
from decimal import Decimal
from app.services.base import BaseIntegration, AssetData

_TOKEN_URL = "https://account.icrypex.com/connect/token"
_BASE = "https://api.icrypex.com"
_WALLET_URL = f"{_BASE}/v1/wallet/spot"
_TICKERS_URL = f"{_BASE}/v1/tickers"
_CLIENT_ID = "coretech9"
_SCOPE = "openid profile email offline_access"


class ICrypexService(BaseIntegration):
    """
    iCrypex entegrasyonu — OAuth2 ROPC (password grant) ile kimlik doğrulama.
    email → api_key alanında, password → api_secret alanında saklanır.
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
            auth_headers = {"Authorization": f"Bearer {token}"}

            wallet_resp = await client.get(_WALLET_URL, headers=auth_headers)
            wallet_resp.raise_for_status()
            wallet = wallet_resp.json()

            ticker_resp = await client.get(_TICKERS_URL)
            ticker_resp.raise_for_status()
            tickers = {t["symbol"]: t for t in ticker_resp.json()}

        assets = []
        items = wallet if isinstance(wallet, list) else wallet.get("content", [])
        for item in items:
            symbol = item.get("asset", "")
            total = Decimal(str(item.get("total", 0) or 0))
            available = Decimal(str(item.get("available", 0) or 0))
            if total <= 0:
                continue

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
                liquid_quantity=available,
                staked_quantity=total - available,
                unit_price_usd=price_usd,
            ))
        return assets

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                token = await self._get_access_token(client)
                r = await client.get(_WALLET_URL, headers={"Authorization": f"Bearer {token}"})
                return r.status_code == 200
        except Exception:
            return False
