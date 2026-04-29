import hashlib
import hmac
import time
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.services.base import BaseExchangeIntegration, AssetData

_BASE_TR = "https://www.binance.tr"
_BASE_GLOBAL = "https://api.binance.com"
_STABLECOIN_USD: dict[str, Decimal] = {
    "USDT": Decimal("1"), "USDC": Decimal("1"),
    "BUSD": Decimal("1"), "FDUSD": Decimal("1"),
    "TRY": Decimal("0"),
}


class BinanceTRService(BaseExchangeIntegration):
    """
    Binance TR (binance.tr) entegrasyonu.
    Bakiye: /open/v1/account/spot (HMAC-SHA256)
    Fiyat: Global Binance /api/v3/ticker/price (USD)
    """

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self._time_offset_ms: int = 0

    async def _sync_time(self, client: httpx.AsyncClient) -> None:
        r = await client.get(f"{_BASE_TR}/open/v1/common/time")
        server_ms = r.json().get("timestamp", int(time.time() * 1000))
        self._time_offset_ms = server_ms - int(time.time() * 1000)

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
        query = urlencode(params)
        sig = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _auth_header(self) -> dict:
        return {"X-MBX-APIKEY": self.api_key}

    async def _get_balances(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        r = await client.get(
            f"{_BASE_TR}/open/v1/account/spot",
            params=self._sign({}),
            headers=self._auth_header(),
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code", 0) != 0:
            raise ValueError(f"Binance TR: {data.get('msg', 'Bilinmeyen hata')}")

        # İki olası format: data.accountAssets veya data (liste)
        inner = data.get("data") or {}
        assets = inner.get("accountAssets", inner) if isinstance(inner, dict) else inner

        balances: dict[str, Decimal] = {}
        for item in (assets if isinstance(assets, list) else []):
            asset = item.get("asset", "")
            free = Decimal(str(item.get("free", 0) or 0))
            locked = Decimal(str(item.get("locked", 0) or 0))
            total = free + locked
            if asset and total > 0:
                balances[asset] = total
        return balances

    async def _get_prices(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        r = await client.get(f"{_BASE_GLOBAL}/api/v3/ticker/price")
        r.raise_for_status()
        return {t["symbol"]: Decimal(t["price"]) for t in r.json()}

    async def fetch(self) -> list[AssetData]:
        async with httpx.AsyncClient(timeout=20) as client:
            await self._sync_time(client)
            balances = await self._get_balances(client)
            prices = await self._get_prices(client)

        btc_price = prices.get("BTCUSDT", Decimal(0))

        def price_of(symbol: str) -> Decimal:
            if symbol in _STABLECOIN_USD:
                return _STABLECOIN_USD[symbol]
            if f"{symbol}USDT" in prices:
                return prices[f"{symbol}USDT"]
            btc_pair = prices.get(f"{symbol}BTC", Decimal(0))
            if btc_pair and btc_price:
                return (btc_pair * btc_price).quantize(Decimal("0.00000001"))
            return Decimal(0)

        assets = []
        for symbol, qty in balances.items():
            unit_price = price_of(symbol)
            if unit_price == 0 and symbol not in _STABLECOIN_USD:
                continue
            assets.append(AssetData(
                symbol=symbol,
                name=symbol,
                provider="binancetr",
                asset_type="crypto",
                source_type="exchange",
                liquid_quantity=qty,
                staked_quantity=Decimal(0),
                unit_price_usd=unit_price,
            ))
        return assets

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await self._sync_time(client)
                r = await client.get(
                    f"{_BASE_TR}/open/v1/account/spot",
                    params=self._sign({}),
                    headers=self._auth_header(),
                )
                data = r.json()
                return data.get("code") == 0
        except Exception:
            return False
