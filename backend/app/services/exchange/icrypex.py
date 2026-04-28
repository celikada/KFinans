import httpx
from decimal import Decimal
from app.services.base import BaseIntegration, AssetData

_BASE = "https://api.icrypex.com"
_TICKERS_URL = f"{_BASE}/v1/tickers"
_WALLET_URL = f"{_BASE}/v1/wallet/spot"


class ICrypexService(BaseIntegration):
    """
    iCrypex Global entegrasyonu.
    Auth: API key doğrudan Bearer token olarak kullanılır.
    Fiyat: /v1/tickers (public) — USDT bazlı fiyatlar USD olarak işlenir.
    Bakiye: /v1/wallet/spot (private)
    """

    def __init__(self, api_key: str):
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def fetch(self) -> list[AssetData]:
        async with httpx.AsyncClient(timeout=15) as client:
            wallet_resp = await client.get(_WALLET_URL, headers=self._headers)
            wallet_resp.raise_for_status()
            wallet = wallet_resp.json()

            ticker_resp = await client.get(_TICKERS_URL)
            ticker_resp.raise_for_status()
            tickers = {t["symbol"]: t for t in ticker_resp.json()}

        assets = []
        for item in wallet.get("content", wallet if isinstance(wallet, list) else []):
            symbol = item.get("asset", "")
            total = Decimal(str(item.get("total", 0) or 0))
            available = Decimal(str(item.get("available", 0) or 0))
            if total <= 0:
                continue

            # USDT bazlı fiyat ara: SYMBOL/USDT
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
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(_WALLET_URL, headers=self._headers)
                return r.status_code == 200
        except Exception:
            return False
