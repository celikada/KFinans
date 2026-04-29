import asyncio
import logging
import httpx
from decimal import Decimal
from app.services.base import BaseIntegration, AssetData

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://account.icrypex.com/connect/token"
_BASE = "https://api.icrypex.com"
_SPOT_URL = f"{_BASE}/v1/wallet/spot"
_EARN_URL = f"{_BASE}/v1/user-earn"
_TICKERS_URL = f"{_BASE}/v1/tickers"
_CLIENT_ID = "coretech9"
_SCOPE = "openid profile email offline_access"
_EARN_INCLUDE = {"Earn", "Redemption"}  # Completed = zaten spot'a aktarılmış, çift sayılmaması için hariç
_STABLECOIN_USD = {"USDT": Decimal("1"), "USDC": Decimal("1"), "BUSD": Decimal("1"), "DAI": Decimal("1")}


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

    def _parse_spot(self, data) -> dict[str, dict]:
        items = data if isinstance(data, list) else data.get("content", [])
        balances: dict[str, dict] = {}
        for item in items:
            symbol = str(item.get("asset", "")).strip().upper()
            total = Decimal(str(item.get("total", 0) or 0))
            available = Decimal(str(item.get("available", total) or total))
            if symbol and total > 0:
                balances[symbol] = {"liquid": available, "staked": total - available}
        return balances

    def _apply_earn(self, balances: dict[str, dict], earn_data: list) -> None:
        for item in earn_data:
            if item.get("status") not in _EARN_INCLUDE:
                continue
            symbol = str(item.get("assetSymbol", "")).strip().upper()
            locked = Decimal(str(item.get("quantity", 0) or 0)) + Decimal(str(item.get("rewardQuantity", 0) or 0))
            if not symbol or locked <= 0:
                continue
            if symbol in balances:
                balances[symbol]["staked"] += locked
            else:
                balances[symbol] = {"liquid": Decimal(0), "staked": locked}

    def _price(self, symbol: str, tickers: dict) -> Decimal:
        if symbol in _STABLECOIN_USD:
            return _STABLECOIN_USD[symbol]
        ticker = tickers.get(f"{symbol}USDT", {})
        return Decimal(str(ticker.get("last", 0) or 0))

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
        balances = self._parse_spot(spot_resp.json())
        if earn_resp.status_code == 200:
            self._apply_earn(balances, earn_resp.json())

        return [
            AssetData(
                symbol=sym,
                name=sym,
                provider="icrypex",
                asset_type="crypto",
                source_type="exchange",
                liquid_quantity=bal["liquid"],
                staked_quantity=bal["staked"],
                unit_price_usd=self._price(sym, tickers),
            )
            for sym, bal in balances.items()
        ]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                token = await self._get_access_token(client)
                r = await client.get(_SPOT_URL, headers={"Authorization": f"Bearer {token}"})
                return r.status_code == 200
        except Exception:
            return False


