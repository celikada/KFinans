import ccxt.async_support as ccxt
from decimal import Decimal
from app.services.base import BaseExchangeIntegration, AssetData


class BinanceService(BaseExchangeIntegration):

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self._client = ccxt.binance({"apiKey": api_key, "secret": api_secret})

    async def fetch(self) -> list[AssetData]:
        try:
            balance = await self._client.fetch_balance()
            assets = []
            for symbol, amounts in balance["total"].items():
                if amounts <= 0:
                    continue
                ticker = None
                try:
                    ticker = await self._client.fetch_ticker(f"{symbol}/USDT")
                except Exception:
                    pass
                assets.append(AssetData(
                    symbol=symbol,
                    name=symbol,
                    provider="binance",
                    asset_type="crypto",
                    source_type="exchange",
                    liquid_quantity=Decimal(str(amounts)),
                    unit_price_usd=Decimal(str(ticker["last"])) if ticker else Decimal(0),
                ))
            return assets
        finally:
            await self._client.close()

    async def health_check(self) -> bool:
        try:
            await self._client.fetch_balance()
            return True
        except Exception:
            return False
        finally:
            await self._client.close()
