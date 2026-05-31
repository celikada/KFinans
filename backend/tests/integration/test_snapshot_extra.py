"""Snapshot servisi (app/services/snapshot.py) icin genis kapsamli birim+entegrasyon
testleri.

Snapshot helper'lari (_gather_*) ve compute_and_save_snapshot dogrudan DB session
+ ORM nesneleriyle cagrilir; HTTP API katmani (register/login email gonderimi)
es gecilir. Dis HTTP cagrilari (TCMB, exchangerate-api, Binance, CoinGecko,
TEFAS, Yahoo) respx ile mock'lanir.

Bu dosya snapshot.py'nin paralel toplama, fiyat enrichment, health_issues
(eksik/stale fiyat, kismi fail) ve _gather_* dispatch yollarini hedefler.
"""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
import respx
from httpx import Response

from app.models.bes import BesHolding
from app.models.cash import CashHolding
from app.models.commodity import CommodityHolding
from app.models.integration import Integration, WalletAddress
from app.models.manual_crypto import ManualCryptoHolding
from app.models.portfolio import AssetPosition, PortfolioSnapshot
from app.models.stock import StockHolding
from app.models.tefas import TefasHolding
from app.models.user import User
from app.services import aggregator, commodity
from app.services import snapshot as snap
from app.services.aggregator import (
    _BINANCE_PRICE_URL,
    _COINGECKO_LIST_URL,
    _COINGECKO_PRICE_URL,
    EXCHANGERATE_API_GBP,
    EXCHANGERATE_API_USD,
    TCMB_URL,
)
from app.services.base import AssetData
from app.services.tefas import _EXPORT_URL

# ── TCMB XML (USD=40, GBP=50) — kur fallback'i deterministik kilar ────────────
_TCMB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date>
  <Currency CurrencyCode="USD"><Unit>1</Unit><ForexBuying>40.000000</ForexBuying></Currency>
  <Currency CurrencyCode="GBP"><Unit>1</Unit><ForexBuying>50.000000</ForexBuying></Currency>
  <Currency CurrencyCode="EUR"><Unit>1</Unit><ForexBuying>44.000000</ForexBuying></Currency>
</Tarih_Date>
"""


def _mock_rates(rsx):
    rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML))
    rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(200, json={"rates": {"TRY": 40.0}}))
    rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json={"rates": {"USD": 1.25}}))


@pytest.fixture(autouse=True)
def _reset_caches():
    aggregator._tcmb_cache = None
    aggregator._coingecko_list_cache = None
    commodity._price_cache = None
    yield
    aggregator._tcmb_cache = None
    aggregator._coingecko_list_cache = None
    commodity._price_cache = None


@pytest_asyncio.fixture
async def user(db):
    """Email gondermeden dogrudan DB'ye dogrulanmis kullanici ekler."""
    u = User(
        email=f"snapx-{uuid.uuid4().hex[:10]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ─────────────────────────────────────────────────────────────────────────────
# _gather_cash_assets — multi-currency + fallback yollari (snapshot 184-231)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherCashAssets:
    async def test_empty_returns_empty(self):
        assert await snap._gather_cash_assets([], Decimal("40"), {}, []) == []

    async def test_try_passthrough(self):
        h = CashHolding(label="Vadesiz", amount=Decimal("1000"), currency="try")
        out = await snap._gather_cash_assets([h], Decimal("40"), {}, [])
        assert len(out) == 1
        assert out[0].unit_price_tl == Decimal("1000")
        assert out[0].asset_type == "cash"
        assert out[0].symbol == "TRY"

    async def test_eur_via_tcmb_rates(self):
        h = CashHolding(label="EUR Hesap", amount=Decimal("100"), currency="EUR")
        rates = {"EUR": Decimal("44")}
        out = await snap._gather_cash_assets([h], Decimal("40"), rates, [])
        assert out[0].unit_price_tl == Decimal("4400.00")

    async def test_usd_via_usd_tl_fallback_when_no_tcmb(self):
        h = CashHolding(label="USD", amount=Decimal("50"), currency="USD")
        out = await snap._gather_cash_assets([h], Decimal("40"), {}, [])
        assert out[0].unit_price_tl == Decimal("2000.00")

    async def test_unknown_currency_uses_usd_approx_with_warning(self):
        h = CashHolding(label="CHF", amount=Decimal("10"), currency="CHF")
        issues: list[dict] = []
        out = await snap._gather_cash_assets([h], Decimal("40"), {}, issues)
        assert out[0].unit_price_tl == Decimal("400.00")
        assert any(i["code"] == "currency_rate_missing" for i in issues)

    async def test_currency_unavailable_when_no_rates_at_all(self):
        h = CashHolding(label="JPY", amount=Decimal("1000"), currency="JPY")
        issues: list[dict] = []
        out = await snap._gather_cash_assets([h], Decimal("0"), {}, issues)
        assert out == []
        assert any(i["code"] == "rate_unavailable" for i in issues)

    async def test_zero_or_negative_skipped(self):
        h = CashHolding(label="Bos", amount=Decimal("0"), currency="TRY")
        out = await snap._gather_cash_assets([h], Decimal("40"), {}, [])
        assert out == []


# ─────────────────────────────────────────────────────────────────────────────
# _gather_commodity_assets (snapshot 244-312)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherCommodityAssets:
    async def test_empty(self):
        assert await snap._gather_commodity_assets([], []) == []

    async def test_gold_gram_with_yahoo_mock(self):
        h = CommodityHolding(unit_type="gram", metal="gold", quantity=Decimal("10"))
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML))
            rsx.get(url__regex=r".*/chart/XAU=X.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 3000.0}}]}}))
            rsx.get(url__regex=r".*/chart/XAG=X.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 35.0}}]}}))
            out = await snap._gather_commodity_assets([h], [])
        assert len(out) == 1
        assert out[0].symbol == "XAU"
        assert out[0].asset_type == "commodity"
        assert out[0].unit_price_tl > 0

    async def test_metal_price_fetch_failure_records_issue(self, monkeypatch):
        async def _boom():
            raise RuntimeError("metal down")

        monkeypatch.setattr("app.services.commodity.fetch_metal_prices", _boom)
        h = CommodityHolding(unit_type="gram", metal="gold", quantity=Decimal("10"))
        issues: list[dict] = []
        out = await snap._gather_commodity_assets([h], issues)
        assert out == []
        assert any(i["code"] == "metal_price_failed" for i in issues)

    async def test_gold_zero_and_silver_zero_issues(self, monkeypatch):
        async def _zero():
            return {"gold": Decimal("0"), "silver": Decimal("0")}

        monkeypatch.setattr("app.services.commodity.fetch_metal_prices", _zero)
        gold = CommodityHolding(unit_type="gram", metal="gold", quantity=Decimal("1"))
        silver = CommodityHolding(unit_type="gram", metal="silver", quantity=Decimal("1"))
        issues: list[dict] = []
        out = await snap._gather_commodity_assets([gold, silver], issues)
        assert out == []  # 0 fiyatta deger 0 → eklenmez
        codes = {i["code"] for i in issues}
        assert "gold_zero" in codes
        assert "silver_zero" in codes

    async def test_biga_and_coin_naming(self, monkeypatch):
        async def _prices():
            return {"gold": Decimal("1000"), "silver": Decimal("50")}

        monkeypatch.setattr("app.services.commodity.fetch_metal_prices", _prices)
        biga = CommodityHolding(unit_type="biga", metal="gold", biga_code="A01", quantity=Decimal("2"))
        coin = CommodityHolding(unit_type="coin", metal="gold", coin_type="ceyrek", quantity=Decimal("1"))
        out = await snap._gather_commodity_assets([biga, coin], [])
        names = {a.name for a in out}
        assert any("A01" in n for n in names)
        assert any("Çeyrek" in n for n in names)

    async def test_invalid_holding_skipped(self, monkeypatch):
        async def _prices():
            return {"gold": Decimal("1000"), "silver": Decimal("50")}

        monkeypatch.setattr("app.services.commodity.fetch_metal_prices", _prices)
        # gecersiz biga_code → calculate_holding_value ValueError → skip
        bad = CommodityHolding(unit_type="biga", metal="gold", biga_code="ZZZ", quantity=Decimal("1"))
        bad.id = 999
        out = await snap._gather_commodity_assets([bad], [])
        assert out == []


# ─────────────────────────────────────────────────────────────────────────────
# _gather_tefas_assets (snapshot 153-167)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherTefasAssets:
    async def test_empty(self):
        assert await snap._gather_tefas_assets([], []) == []

    async def test_success(self):
        h = TefasHolding(code="YAC", quantity=Decimal("100"), name="Test")
        with respx.mock(assert_all_called=False) as rsx:
            rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=[{"fonKodu": "YAC", "sonPortfoyDegeri": 100.0, "sonPayAdedi": 80.0}]))
            out = await snap._gather_tefas_assets([h], [])
        assert len(out) == 1
        assert out[0].symbol == "YAC"

    async def test_failure_records_issue(self):
        h = TefasHolding(code="ZZZ", quantity=Decimal("100"), name="Yok")
        issues: list[dict] = []
        with respx.mock(assert_all_called=False) as rsx:
            # bos liste → fon bulunamadi → ValueError → issue
            rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=[]))
            out = await snap._gather_tefas_assets([h], issues)
        assert out == []
        assert any(i["code"] == "fetch_failed" and i["source"] == "tefas" for i in issues)


# ─────────────────────────────────────────────────────────────────────────────
# _gather_stock_assets (snapshot 504-562)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherStockAssets:
    async def test_empty(self):
        assert await snap._gather_stock_assets([], Decimal("40"), Decimal("1.25"), []) == []

    async def test_fetch_failure_records_issue(self, monkeypatch):
        async def _boom(_tickers):
            raise RuntimeError("yahoo down")

        monkeypatch.setattr("app.services.snapshot.fetch_stock_quotes", _boom)
        h = StockHolding(ticker="AAPL", quantity=Decimal("10"), name="Apple")
        issues: list[dict] = []
        out = await snap._gather_stock_assets([h], Decimal("40"), Decimal("1.25"), issues)
        assert out == []
        assert any(i["code"] == "fetch_failed" and i["source"] == "stocks" for i in issues)

    async def test_currency_conversions_and_stale(self, monkeypatch):
        from types import SimpleNamespace

        quotes = {
            "TRY.IS": SimpleNamespace(ticker="TRY.IS", name="Tr", price=Decimal("10"), currency="TRY", is_stale=False, market_state="REGULAR"),
            "AAPL": SimpleNamespace(ticker="AAPL", name="Apple", price=Decimal("100"), currency="USD", is_stale=True, market_state="CLOSED"),
            "LLOY.L": SimpleNamespace(ticker="LLOY.L", name="Lloyds", price=Decimal("5000"), currency="GBp", is_stale=False, market_state="REGULAR"),
            "MISSING": None,
        }

        async def _quotes(_tickers):
            return quotes

        monkeypatch.setattr("app.services.snapshot.fetch_stock_quotes", _quotes)
        holdings = [
            StockHolding(ticker="TRY.IS", quantity=Decimal("1"), name="Tr"),
            StockHolding(ticker="AAPL", quantity=Decimal("1"), name="Apple"),
            StockHolding(ticker="LLOY.L", quantity=Decimal("1"), name="Lloyds"),
            StockHolding(ticker="MISSING", quantity=Decimal("1"), name="Yok"),
        ]
        issues: list[dict] = []
        out = await snap._gather_stock_assets(holdings, Decimal("40"), Decimal("1.25"), issues)
        by_sym = {a.symbol: a for a in out}
        assert "MISSING" not in by_sym  # None quote → skip
        assert by_sym["TRY.IS"].unit_price_tl == Decimal("10.0000")
        # USD: 100 * 40 = 4000
        assert by_sym["AAPL"].unit_price_tl == Decimal("4000.0000")
        # GBp: (5000/100) * 1.25 * 40 = 2500
        assert by_sym["LLOY.L"].unit_price_tl == Decimal("2500.0000")
        assert any(i["code"] == "stale_price" for i in issues)


# ─────────────────────────────────────────────────────────────────────────────
# _gather_crypto_assets (snapshot 58-87)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherCryptoAssets:
    async def test_unknown_provider_skipped(self):
        intg = Integration(provider="unknown", encrypted_key=None, encrypted_secret=None)
        out = await snap._gather_crypto_assets([intg], [])
        assert out == []

    async def test_binance_service_dispatch_failure_records_issue(self, monkeypatch):
        from app.core import security

        monkeypatch.setattr(security, "decrypt_secret", lambda v: "plain")
        monkeypatch.setattr("app.services.snapshot.decrypt_secret", lambda v: "plain")

        class _FakeSvc:
            def __init__(self, *a, **k):
                pass

            async def fetch(self):
                raise RuntimeError("binance auth fail")

        monkeypatch.setattr("app.services.snapshot.BinanceService", _FakeSvc)
        intg = Integration(provider="binance", encrypted_key="k", encrypted_secret="s")
        issues: list[dict] = []
        out = await snap._gather_crypto_assets([intg], issues)
        assert out == []
        assert any(i["source"] == "crypto" and i["code"] == "fetch_failed" for i in issues)

    async def test_binance_success(self, monkeypatch):
        monkeypatch.setattr("app.services.snapshot.decrypt_secret", lambda v: "plain")

        class _FakeSvc:
            def __init__(self, *a, **k):
                pass

            async def fetch(self):
                return [
                    AssetData(
                        symbol="BTC",
                        name="Bitcoin",
                        provider="binance",
                        asset_type="crypto",
                        source_type="exchange",
                        liquid_quantity=Decimal("1"),
                        unit_price_usd=Decimal("50000"),
                    )
                ]

        monkeypatch.setattr("app.services.snapshot.BinanceService", _FakeSvc)
        intg = Integration(provider="binance", encrypted_key="k", encrypted_secret="s")
        out = await snap._gather_crypto_assets([intg], [])
        assert len(out) == 1 and out[0].symbol == "BTC"

    async def test_icrypex_and_binancetr_dispatch(self, monkeypatch):
        monkeypatch.setattr("app.services.snapshot.decrypt_secret", lambda v: "plain" if v else "")

        seen = []

        def _make(name):
            class _S:
                def __init__(self, *a, **k):
                    seen.append(name)

                async def fetch(self):
                    return []

            return _S

        monkeypatch.setattr("app.services.snapshot.ICrypexService", _make("icrypex"))
        monkeypatch.setattr("app.services.snapshot.BinanceTRService", _make("binancetr"))
        btr = Integration(provider="binancetr", encrypted_key="k", encrypted_secret="s")
        # Integration modelinde encrypted_extra kolonu yok; snapshot kodu getattr
        # ile okur — branch'i kapatmak icin instance attribute ekle.
        btr.encrypted_extra = "e"
        intgs = [
            Integration(provider="icrypex", encrypted_key="k", encrypted_secret="s"),
            btr,
        ]
        await snap._gather_crypto_assets(intgs, [])
        assert "icrypex" in seen and "binancetr" in seen


# ─────────────────────────────────────────────────────────────────────────────
# _gather_wallet_assets (snapshot 90-146)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherWalletAssets:
    def _wallet(self, chain):
        return WalletAddress(chain=chain, address="0x" + "a" * 40)

    async def test_unknown_chain_returns_empty(self):
        w = self._wallet("dogecoin")
        out = await snap._gather_wallet_assets([w], [])
        assert out == []

    async def test_empty_result_records_issue(self, monkeypatch):
        class _Empty:
            def __init__(self, *a, **k):
                pass

            async def fetch(self):
                return []

        monkeypatch.setattr("app.services.snapshot.EthereumService", _Empty)
        w = self._wallet("ethereum")
        issues: list[dict] = []
        out = await snap._gather_wallet_assets([w], issues)
        assert out == []
        assert any(i["code"] == "empty_result" for i in issues)

    async def test_fetch_exception_records_issue(self, monkeypatch):
        class _Boom:
            def __init__(self, *a, **k):
                pass

            async def fetch(self):
                raise RuntimeError("rpc down")

        monkeypatch.setattr("app.services.snapshot.BitcoinService", _Boom)
        w = self._wallet("bitcoin")
        issues: list[dict] = []
        out = await snap._gather_wallet_assets([w], issues)
        assert out == []
        assert any(i["code"] == "fetch_failed" and i["source"] == "wallet" for i in issues)

    async def test_success(self, monkeypatch):
        class _Ok:
            def __init__(self, *a, **k):
                pass

            async def fetch(self):
                return [
                    AssetData(
                        symbol="ETH",
                        name="Ethereum",
                        provider="ethereum",
                        asset_type="crypto",
                        source_type="wallet",
                        liquid_quantity=Decimal("2"),
                        unit_price_usd=Decimal("3000"),
                    )
                ]

        monkeypatch.setattr("app.services.snapshot.EthereumService", _Ok)
        w = self._wallet("ethereum")
        out = await snap._gather_wallet_assets([w], [])
        assert len(out) == 1 and out[0].symbol == "ETH"

    @pytest.mark.parametrize(
        "chain,service_name",
        [
            ("sonic", "SonicService"),
            ("avalanche_p", "AvalanchePChainService"),
            ("avalanche_c", "AvalancheCChainService"),
            ("solana", "SolanaService"),
            ("litecoin", "LitecoinService"),
            ("algorand", "AlgorandService"),
            ("cardano", "CardanoService"),
            ("polkadot", "PolkadotService"),
        ],
    )
    async def test_all_chain_dispatch_paths(self, monkeypatch, chain, service_name):
        """Her zincir dispatch dali (snapshot 97-116) icin servis secimi calismali."""

        class _Ok:
            def __init__(self, *a, **k):
                pass

            async def fetch(self):
                return [
                    AssetData(
                        symbol="TKN",
                        name="Token",
                        provider=chain,
                        asset_type="crypto",
                        source_type="wallet",
                        liquid_quantity=Decimal("1"),
                        unit_price_usd=Decimal("10"),
                    )
                ]

        monkeypatch.setattr(f"app.services.snapshot.{service_name}", _Ok)
        w = self._wallet(chain)
        out = await snap._gather_wallet_assets([w], [])
        assert len(out) == 1 and out[0].symbol == "TKN"


# ─────────────────────────────────────────────────────────────────────────────
# _gather_bes_assets (sync, snapshot 482-501)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherBesAssets:
    def test_maps_total_value(self):
        h = BesHolding(
            plan_name="Plan A",
            paid_principal=Decimal("100"),
            paid_returns=Decimal("20"),
            govt_contribution=Decimal("30"),
            govt_returns=Decimal("5"),
        )
        out = snap._gather_bes_assets([h])
        assert len(out) == 1
        assert out[0].asset_type == "pension"
        assert out[0].provider == "bes"
        assert out[0].unit_price_tl == Decimal("155")


# ─────────────────────────────────────────────────────────────────────────────
# _gather_manual_crypto_assets (snapshot 315-479)
# ─────────────────────────────────────────────────────────────────────────────
class TestGatherManualCryptoAssets:
    async def test_empty(self):
        assert await snap._gather_manual_crypto_assets([], []) == []

    async def test_manual_price_present(self):
        h = ManualCryptoHolding(
            exchange="btcturk",
            symbol="BTC",
            quantity=Decimal("1"),
            price_source="manual",
            manual_unit_price_tl=Decimal("2000000"),
        )
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            issues: list[dict] = []
            out = await snap._gather_manual_crypto_assets([h], issues)
        assert out[0].unit_price_tl == Decimal("2000000")
        assert any(i["code"] == "info_manual_price" for i in issues)

    async def test_manual_price_missing_warning(self):
        h = ManualCryptoHolding(exchange="btcturk", symbol="BTC", quantity=Decimal("1"), price_source="manual", manual_unit_price_tl=None)
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            issues: list[dict] = []
            out = await snap._gather_manual_crypto_assets([h], issues)
        assert out[0].unit_price_tl == Decimal("0")
        assert any(i["code"] == "manual_price_missing" for i in issues)

    async def test_linked_commodity_gold(self, monkeypatch):
        async def _metal():
            return {"gold": Decimal("4000"), "silver": Decimal("50")}

        monkeypatch.setattr("app.services.commodity.fetch_metal_prices", _metal)
        h = ManualCryptoHolding(exchange="x", symbol="GOLD", quantity=Decimal("2"), price_source="linked", linked_source="commodity", linked_id="XAU")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            issues: list[dict] = []
            out = await snap._gather_manual_crypto_assets([h], issues)
        assert out[0].unit_price_tl == Decimal("4000")
        assert any(i["code"] == "info_linked" for i in issues)

    async def test_linked_binance(self, monkeypatch):
        async def _combined(ids):
            return {"ETH": Decimal("3000")}

        monkeypatch.setattr("app.services.snapshot.fetch_combined_prices", _combined)
        h = ManualCryptoHolding(exchange="x", symbol="ETH", quantity=Decimal("1"), price_source="linked", linked_source="binance", linked_id="ETH")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        # 3000 USD * 40 USD/TL = 120000
        assert out[0].unit_price_tl == Decimal("120000.0000")

    async def test_linked_coingecko(self, monkeypatch):
        async def _cg(ids):
            return {"tether-gold": Decimal("2500")}

        monkeypatch.setattr("app.services.aggregator.fetch_coingecko_prices_by_ids", _cg)
        h = ManualCryptoHolding(exchange="x", symbol="XAUT", quantity=Decimal("1"), price_source="linked", linked_source="coingecko", linked_id="tether-gold")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        assert out[0].unit_price_tl == Decimal("100000.0000")

    async def test_linked_tefas(self, monkeypatch):
        async def _tefas(codes):
            return {"AFA": Decimal("12.5")}

        monkeypatch.setattr("app.services.tefas.fetch_tefas_prices_by_codes", _tefas)
        h = ManualCryptoHolding(exchange="x", symbol="AFA", quantity=Decimal("10"), price_source="linked", linked_source="tefas", linked_id="AFA")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        assert out[0].unit_price_tl == Decimal("12.5")

    async def test_linked_invalid_source(self):
        h = ManualCryptoHolding(exchange="x", symbol="ZZZ", quantity=Decimal("1"), price_source="linked", linked_source="nope", linked_id="ZZZ")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            issues: list[dict] = []
            out = await snap._gather_manual_crypto_assets([h], issues)
        assert out[0].unit_price_tl == Decimal("0")
        assert any(i["code"] == "linked_invalid" for i in issues)

    async def test_linked_no_price_warning(self, monkeypatch):
        async def _tefas(codes):
            return {}

        monkeypatch.setattr("app.services.tefas.fetch_tefas_prices_by_codes", _tefas)
        h = ManualCryptoHolding(exchange="x", symbol="AFA", quantity=Decimal("1"), price_source="linked", linked_source="tefas", linked_id="AFA")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            issues: list[dict] = []
            await snap._gather_manual_crypto_assets([h], issues)
        assert any(i["code"] == "linked_tefas_no_price" for i in issues)

    async def test_linked_metal_fetch_failure(self, monkeypatch):
        async def _boom():
            raise RuntimeError("down")

        monkeypatch.setattr("app.services.commodity.fetch_metal_prices", _boom)
        h = ManualCryptoHolding(exchange="x", symbol="GOLD", quantity=Decimal("1"), price_source="linked", linked_source="commodity", linked_id="XAU")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            issues: list[dict] = []
            await snap._gather_manual_crypto_assets([h], issues)
        assert any(i["code"] == "metal_price_failed" for i in issues)

    async def test_auto_leaves_zero_price(self):
        h = ManualCryptoHolding(exchange="x", symbol="DOGE", quantity=Decimal("100"), price_source="auto")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        assert out[0].unit_price_tl == Decimal("0")

    async def test_linked_binance_fetch_exception_swallowed(self, monkeypatch):
        async def _boom(ids):
            raise RuntimeError("binance down")

        monkeypatch.setattr("app.services.snapshot.fetch_combined_prices", _boom)
        h = ManualCryptoHolding(exchange="x", symbol="ETH", quantity=Decimal("1"), price_source="linked", linked_source="binance", linked_id="ETH")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        # fiyat alinamadi → 0
        assert out[0].unit_price_tl == Decimal("0")

    async def test_linked_coingecko_fetch_exception_swallowed(self, monkeypatch):
        async def _boom(ids):
            raise RuntimeError("cg down")

        monkeypatch.setattr("app.services.aggregator.fetch_coingecko_prices_by_ids", _boom)
        h = ManualCryptoHolding(exchange="x", symbol="XAUT", quantity=Decimal("1"), price_source="linked", linked_source="coingecko", linked_id="tether-gold")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        assert out[0].unit_price_tl == Decimal("0")

    async def test_linked_tefas_fetch_exception_swallowed(self, monkeypatch):
        async def _boom(codes):
            raise RuntimeError("tefas down")

        monkeypatch.setattr("app.services.tefas.fetch_tefas_prices_by_codes", _boom)
        h = ManualCryptoHolding(exchange="x", symbol="AFA", quantity=Decimal("1"), price_source="linked", linked_source="tefas", linked_id="AFA")
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            out = await snap._gather_manual_crypto_assets([h], [])
        assert out[0].unit_price_tl == Decimal("0")

    async def test_usd_tl_failure_handled(self, monkeypatch):
        """fetch_usd_to_tl patlarsa usd_tl=0 ile devam (snapshot 384-385)."""

        async def _boom():
            raise RuntimeError("no usd rate")

        monkeypatch.setattr("app.services.snapshot.fetch_usd_to_tl", _boom)
        h = ManualCryptoHolding(exchange="x", symbol="ETH", quantity=Decimal("1"), price_source="linked", linked_source="binance", linked_id="ETH")

        async def _combined(ids):
            return {"ETH": Decimal("3000")}

        monkeypatch.setattr("app.services.snapshot.fetch_combined_prices", _combined)
        out = await snap._gather_manual_crypto_assets([h], [])
        # usd_tl=0 → unit_tl 0 kalir
        assert out[0].unit_price_tl == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# _last_known_usd_price (snapshot 565-600)
# ─────────────────────────────────────────────────────────────────────────────
class TestLastKnownUsdPrice:
    async def test_no_history_returns_none(self, db, user):
        price, dt = await snap._last_known_usd_price(db, user.id, "BTC")
        assert price is None and dt is None

    async def test_returns_last_price_from_snapshot(self, db, user):
        from datetime import date

        ps = PortfolioSnapshot(
            user_id=user.id,
            snapshot_date=date(2026, 1, 1),
            total_value_tl=Decimal("100"),
            usd_try_rate=Decimal("40"),
        )
        db.add(ps)
        await db.flush()
        pos = AssetPosition(
            snapshot_id=ps.id,
            source_type="exchange",
            provider="binance",
            asset_type="crypto",
            symbol="BTC",
            name="Bitcoin",
            liquid_quantity=Decimal("1"),
            staked_quantity=Decimal("0"),
            pending_rewards=Decimal("0"),
            unit_price_tl=Decimal("400000"),
            total_value_tl=Decimal("400000"),
            weight_pct=Decimal("100"),
        )
        db.add(pos)
        await db.commit()
        price, dt = await snap._last_known_usd_price(db, user.id, "BTC")
        # 400000 TL / 40 = 10000 USD
        assert price == Decimal("10000.000000")
        assert dt == date(2026, 1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# compute_and_save_snapshot — uctan uca (snapshot 603-794)
# ─────────────────────────────────────────────────────────────────────────────
class TestComputeAndSaveSnapshot:
    async def test_empty_user_zero_total(self, db, user):
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            result = await snap.compute_and_save_snapshot(user.id, db)
        assert isinstance(result, PortfolioSnapshot)
        assert result.total_value_tl == Decimal("0.00")

    async def test_dry_run_does_not_persist(self, db, user):
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            result = await snap.compute_and_save_snapshot(user.id, db, dry_run=True)
        assert isinstance(result, dict)
        assert result["saved"] is False
        assert result["asset_count"] == 0
        assert result["usd_try_rate"] == "40.000000"
        from sqlalchemy import select

        rows = (await db.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == user.id))).scalars().all()
        assert rows == []

    async def test_usd_rate_failure_raises(self, db, user):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(503))
            rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(500))
            rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json={"rates": {"USD": 1.25}}))
            with pytest.raises(RuntimeError, match="USD/TRY"):
                await snap.compute_and_save_snapshot(user.id, db)

    async def test_idempotent_same_day(self, db, user):
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            first = await snap.compute_and_save_snapshot(user.id, db)
            second = await snap.compute_and_save_snapshot(user.id, db)
        assert first.id != second.id
        from sqlalchemy import select

        rows = (await db.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == user.id))).scalars().all()
        assert len(rows) == 1

    async def test_gbp_failure_continues(self, db, user):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML))
            rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(500))
            result = await snap.compute_and_save_snapshot(user.id, db)
        assert isinstance(result, PortfolioSnapshot)

    async def test_bes_and_cash_included_with_total(self, db, user):
        db.add(
            BesHolding(
                user_id=user.id,
                plan_name="Plan",
                paid_principal=Decimal("1000"),
                paid_returns=Decimal("0"),
                govt_contribution=Decimal("0"),
                govt_returns=Decimal("0"),
            )
        )
        db.add(CashHolding(user_id=user.id, label="TL", amount=Decimal("500"), currency="TRY"))
        await db.commit()
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            result = await snap.compute_and_save_snapshot(user.id, db)
        assert result.total_value_tl == Decimal("1500.00")
        assert result.usd_try_rate == Decimal("40.000000")

    async def test_spot_price_enrichment_for_auto_crypto(self, db, user):
        db.add(ManualCryptoHolding(user_id=user.id, exchange="x", symbol="BTC", quantity=Decimal("1"), price_source="auto"))
        await db.commit()
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}]))
            result = await snap.compute_and_save_snapshot(user.id, db)
        # 1 BTC * 60000 USD * 40 = 2,400,000 TL
        assert result.total_value_tl == Decimal("2400000.00")

    async def test_no_spot_price_records_issue(self, db, user):
        db.add(ManualCryptoHolding(user_id=user.id, exchange="x", symbol="OBSCURE", quantity=Decimal("5"), price_source="auto"))
        await db.commit()
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[]))
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=[]))
            result = await snap.compute_and_save_snapshot(user.id, db)
        assert result.health_issues is not None
        assert any(i["code"] == "no_spot_price" for i in result.health_issues)

    async def test_stale_price_fallback_from_previous_snapshot(self, db, user):
        from datetime import date

        # Onceki snapshot — OBSCURE icin son bilinen fiyat (400 TL @ 40 = 10 USD)
        ps = PortfolioSnapshot(user_id=user.id, snapshot_date=date(2026, 1, 1), total_value_tl=Decimal("400"), usd_try_rate=Decimal("40"))
        db.add(ps)
        await db.flush()
        db.add(
            AssetPosition(
                snapshot_id=ps.id,
                source_type="manual",
                provider="manual:x",
                asset_type="crypto",
                symbol="OBSCURE",
                name="O",
                liquid_quantity=Decimal("1"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_tl=Decimal("400"),
                total_value_tl=Decimal("400"),
                weight_pct=Decimal("100"),
            )
        )
        db.add(ManualCryptoHolding(user_id=user.id, exchange="x", symbol="OBSCURE", quantity=Decimal("2"), price_source="auto"))
        await db.commit()
        with respx.mock(assert_all_called=False) as rsx:
            _mock_rates(rsx)
            rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[]))
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=[]))
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={}))
            result = await snap.compute_and_save_snapshot(user.id, db)
        assert any(i["code"] == "stale_price" for i in (result.health_issues or []))
