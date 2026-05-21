import asyncio
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.services.base import AssetData, BaseExchangeIntegration

logger = logging.getLogger(__name__)

_BASE_TR = "https://www.binance.tr"
_BASE_GLOBAL = "https://api.binance.com"
_STABLECOIN_USD: dict[str, Decimal] = {
    "USDT": Decimal("1"),
    "USDC": Decimal("1"),
    "BUSD": Decimal("1"),
    "FDUSD": Decimal("1"),
    "TRY": Decimal("0"),
}


class BinanceTRService(BaseExchangeIntegration):
    """
    Binance TR entegrasyonu.

    Spot bakiye: /open/v1/account/spot (API key + HMAC imzası)
    Earn dahil tüm assetler: /bapi/asset/v3/private/asset-service/asset/get-user-asset
        → Bu endpoint cookie tabanlı JWT gerektirir (session_token parametresi).
        → Kullanıcı tarayıcısından kopyaladığı `cid` cookie değerini
          extra_token alanına yapıştırır.
    Fiyat: Global Binance /api/v3/ticker/price
    """

    def __init__(self, api_key: str, api_secret: str, session_token: str = ""):
        super().__init__(api_key, api_secret)
        self.session_token = session_token.strip()
        self._time_offset_ms: int = 0

    async def _sync_time(self, client: httpx.AsyncClient) -> None:
        r = await client.get(f"{_BASE_TR}/open/v1/common/time")
        server_ms = r.json().get("timestamp", int(time.time() * 1000))
        self._time_offset_ms = server_ms - int(time.time() * 1000)

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
        params.setdefault("recvWindow", 60000)
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

        inner = data.get("data") or {}
        assets = inner.get("accountAssets", inner) if isinstance(inner, dict) else inner

        balances: dict[str, Decimal] = {}
        for item in assets if isinstance(assets, list) else []:
            asset = item.get("asset", "")
            free = Decimal(str(item.get("free", 0) or 0))
            locked = Decimal(str(item.get("locked", 0) or 0))
            total = free + locked
            if asset and total > 0:
                balances[asset] = total
        return balances

    async def _get_all_assets_via_session(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        """
        /bapi/ endpoint'i ile spot + earn dahil tüm assetleri çeker.
        Binance TR mobil uygulaması ve web sitesi bu endpoint'i kullanır.
        session_token = tarayıcıdan kopyalanan `cid` cookie değeri.
        """
        r = await client.post(
            f"{_BASE_TR}/bapi/asset/v3/private/asset-service/asset/get-user-asset",
            json={"asset": "", "needBtcValuation": False},
            headers={
                "Authorization": f"Bearer {self.session_token}",
                "Cookie": f"cid={self.session_token}",
                "Content-Type": "application/json",
                "clienttype": "web",
                "lang": "tr-TR",
            },
        )
        if r.status_code != 200:
            raise ValueError(f"Binance TR session token geçersiz veya süresi dolmuş (HTTP {r.status_code})")
        data = r.json()
        if data.get("code") not in (None, "000000", 0):
            raise ValueError(f"Binance TR: {data.get('message', data.get('msg', 'Bilinmeyen hata'))}")

        balances: dict[str, Decimal] = {}
        for item in data.get("data", []):
            asset = item.get("asset", "")
            free = Decimal(str(item.get("free", 0) or 0))
            locked = Decimal(str(item.get("locked", 0) or 0))
            freeze = Decimal(str(item.get("freeze", 0) or 0))
            total = free + locked + freeze
            if asset and total > 0:
                balances[asset] = total
        return balances

    async def _get_flexible_earn(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        balances: dict[str, Decimal] = {}
        current = 1
        while True:
            try:
                r = await client.get(
                    f"{_BASE_TR}/sapi/v1/simple-earn/flexible/position",
                    params=self._sign({"current": current, "size": 100}),
                    headers=self._auth_header(),
                )
                if r.status_code != 200:
                    break
                data = r.json()
                for row in data.get("rows", []):
                    asset = row.get("asset", "")
                    amt = Decimal(str(row.get("totalAmount", 0) or 0))
                    if asset and amt > 0:
                        balances[asset] = balances.get(asset, Decimal(0)) + amt
                if not data.get("hasNextPage"):
                    break
                current += 1
            except Exception:
                break
        return balances

    async def _get_locked_earn(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        balances: dict[str, Decimal] = {}
        current = 0
        while True:
            try:
                r = await client.get(
                    f"{_BASE_TR}/sapi/v1/simple-earn/locked/position",
                    params=self._sign({"current": current, "size": 100}),
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
            except Exception:
                break
        return balances

    async def _get_prices(self, client: httpx.AsyncClient) -> dict[str, Decimal]:
        r = await client.get(f"{_BASE_GLOBAL}/api/v3/ticker/price")
        r.raise_for_status()
        return {t["symbol"]: Decimal(t["price"]) for t in r.json()}

    async def fetch(self) -> list[AssetData]:
        async with httpx.AsyncClient(timeout=20) as client:
            await self._sync_time(client)

            if self.session_token:
                # Session token varsa earn dahil tüm assetleri tek endpoint'ten çek
                all_balances, prices = await asyncio.gather(
                    self._get_all_assets_via_session(client),
                    self._get_prices(client),
                )
                spot = all_balances
                flex_earn: dict[str, Decimal] = {}
                locked_earn: dict[str, Decimal] = {}
            else:
                # Sadece API key varsa spot + sapi earn denemesi
                spot, prices, flex_earn, locked_earn = await asyncio.gather(
                    self._get_balances(client),
                    self._get_prices(client),
                    self._get_flexible_earn(client),
                    self._get_locked_earn(client),
                )

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

        all_symbols = set(spot) | set(flex_earn) | set(locked_earn)
        assets = []
        for symbol in all_symbols:
            liquid = spot.get(symbol, Decimal(0))
            staked = flex_earn.get(symbol, Decimal(0)) + locked_earn.get(symbol, Decimal(0))
            # Session token modunda spot zaten earn dahil tüm varlıkları içerir
            total = liquid + staked
            if total <= 0:
                continue
            unit_price = price_of(symbol)
            if unit_price == 0 and symbol not in _STABLECOIN_USD:
                continue
            assets.append(
                AssetData(
                    symbol=symbol,
                    name=symbol,
                    provider="binancetr",
                    asset_type="crypto",
                    source_type="exchange",
                    liquid_quantity=liquid,
                    staked_quantity=staked,
                    unit_price_usd=unit_price,
                )
            )
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
