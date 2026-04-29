import asyncio
import hashlib
import hmac
import time
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.services.base import BaseExchangeIntegration, AssetData

_BASE = "https://api.binance.com"
_STABLECOIN_USD: dict[str, Decimal] = {
    "USDT": Decimal("1"), "USDC": Decimal("1"),
    "BUSD": Decimal("1"), "FDUSD": Decimal("1"), "DAI": Decimal("1"),
    "TUSD": Decimal("1"), "TRY": Decimal("0"),
}


class BinanceService(BaseExchangeIntegration):

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _auth_header(self) -> dict:
        return {"X-MBX-APIKEY": self.api_key}

    async def _get_all_prices(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        r = await client.get(f"{_BASE}/api/v3/ticker/price")
        r.raise_for_status()
        return {t["symbol"]: Decimal(t["price"]) for t in r.json()}

    async def _get_spot_balances(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        r = await client.get(
            f"{_BASE}/api/v3/account",
            params=self._sign({}),
            headers=self._auth_header(),
        )
        r.raise_for_status()
        return {
            b["asset"]: Decimal(b["free"]) + Decimal(b["locked"])
            for b in r.json()["balances"]
            if Decimal(b["free"]) + Decimal(b["locked"]) > 0
        }

    async def _get_flexible_earn(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        """Simple Earn — esnek ürünler."""
        balances: dict[str, Decimal] = {}
        current = 0
        page_size = 100
        while True:
            r = await client.get(
                f"{_BASE}/sapi/v1/simple-earn/flexible/position",
                params=self._sign({"current": current, "size": page_size}),
                headers=self._auth_header(),
            )
            if r.status_code != 200:
                break
            data = r.json()
            rows = data.get("rows", [])
            for row in rows:
                asset = row.get("asset", "")
                amt = Decimal(str(row.get("totalAmount", 0) or 0))
                if asset and amt > 0:
                    balances[asset] = balances.get(asset, Decimal(0)) + amt
            if not data.get("hasNextPage"):
                break
            current += 1
        return balances

    async def _get_locked_earn(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        """Simple Earn — kilitli ürünler."""
        balances: dict[str, Decimal] = {}
        current = 0
        page_size = 100
        while True:
            r = await client.get(
                f"{_BASE}/sapi/v1/simple-earn/locked/position",
                params=self._sign({"current": current, "size": page_size}),
                headers=self._auth_header(),
            )
            if r.status_code != 200:
                break
            data = r.json()
            for row in data.get("rows", []):
                asset = row.get("asset", "")
                amt = Decimal(str(row.get("amount", 0) or 0))
                if asset and amt > 0:
                    balances[asset] = balances.get(asset, Decimal(0)) + amt
            if not data.get("hasNextPage"):
                break
            current += 1
        return balances

    async def fetch(self) -> list[AssetData]:
        async with httpx.AsyncClient(timeout=20) as client:
            prices_task = asyncio.create_task(self._get_all_prices(client))
            spot_task = asyncio.create_task(self._get_spot_balances(client))

            prices, spot = await asyncio.gather(prices_task, spot_task)

            flex_earn, locked_earn = await asyncio.gather(
                self._get_flexible_earn(client),
                self._get_locked_earn(client),
            )

        def price_of(symbol: str) -> Decimal:
            if symbol in _STABLECOIN_USD:
                return _STABLECOIN_USD[symbol]
            return prices.get(f"{symbol}USDT", Decimal(0))

        all_symbols = set(spot) | set(flex_earn) | set(locked_earn)
        assets = []
        for symbol in all_symbols:
            liquid = spot.get(symbol, Decimal(0))
            staked = flex_earn.get(symbol, Decimal(0)) + locked_earn.get(symbol, Decimal(0))
            total = liquid + staked
            if total <= 0:
                continue
            unit_price = price_of(symbol)
            if unit_price == 0 and symbol not in _STABLECOIN_USD:
                continue
            assets.append(AssetData(
                symbol=symbol,
                name=symbol,
                provider="binance",
                asset_type="crypto",
                source_type="exchange",
                liquid_quantity=liquid,
                staked_quantity=staked,
                unit_price_usd=unit_price,
            ))
        return assets

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{_BASE}/api/v3/account",
                    params=self._sign({}),
                    headers=self._auth_header(),
                )
                return r.status_code == 200
        except Exception:
            return False
