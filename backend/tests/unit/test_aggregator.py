"""
Aggregator finansal formülleri — WoW, MoM, breakdown, weight, staking ekstraksiyonu.
DB veya HTTP gerekmez; saf hesaplama testleri.

Para hesaplarında hata kabul edilmez — bu modül %100 coverage hedefler.
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.aggregator import (
    calculate_breakdown,
    calculate_changes,
    extract_staking_positions,
    to_asset_position,
)
from app.services.base import AssetData


# ─── Yardımcı Factory'ler ─────────────────────────────────────────────────────

def make_position(
    *,
    asset_type: str = "crypto",
    symbol: str = "BTC",
    name: str = "Bitcoin",
    provider: str = "binance",
    source_type: str = "exchange",
    liquid: str = "0",
    staked: str = "0",
    rewards: str = "0",
    unit_price_tl: str = "0",
    total_value_tl: str = "0",
    weight_pct: str = "0",
):
    """Test için AssetPositionOut'a uyumlu obje (Pydantic from_attributes ile)."""
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000000",
        source_type=source_type,
        provider=provider,
        asset_type=asset_type,
        symbol=symbol,
        name=name,
        liquid_quantity=Decimal(liquid),
        staked_quantity=Decimal(staked),
        pending_rewards=Decimal(rewards),
        unit_price_tl=Decimal(unit_price_tl),
        total_value_tl=Decimal(total_value_tl),
        weight_pct=Decimal(weight_pct),
    )


def make_snapshot(total: str, *positions, snapshot_date_offset: int = 0):
    return SimpleNamespace(
        total_value_tl=Decimal(total),
        snapshot_date=date(2026, 4, 26) - timedelta(weeks=snapshot_date_offset),
        asset_positions=list(positions),
    )


# ─── calculate_changes (WoW, MoM) ─────────────────────────────────────────────

class TestCalculateChanges:
    def test_no_history_returns_zero_changes(self):
        snap = make_snapshot("100000")
        result = calculate_changes([snap])
        assert result.current_value_tl == Decimal("100000")
        assert result.wow_change_tl == Decimal("0")
        assert result.wow_change_pct == Decimal("0.00")
        assert result.mom_change_tl == Decimal("0")

    def test_wow_calculation_positive(self):
        current = make_snapshot("110000")
        prev_week = make_snapshot("100000", snapshot_date_offset=1)
        result = calculate_changes([current, prev_week])
        assert result.wow_change_tl == Decimal("10000")
        assert result.wow_change_pct == Decimal("10.00")

    def test_wow_calculation_negative(self):
        current = make_snapshot("90000")
        prev_week = make_snapshot("100000", snapshot_date_offset=1)
        result = calculate_changes([current, prev_week])
        assert result.wow_change_tl == Decimal("-10000")
        assert result.wow_change_pct == Decimal("-10.00")

    def test_wow_zero_previous_does_not_divide_by_zero(self):
        current = make_snapshot("50000")
        prev_week = make_snapshot("0", snapshot_date_offset=1)
        result = calculate_changes([current, prev_week])
        assert result.wow_change_tl == Decimal("50000")
        assert result.wow_change_pct == Decimal("0.00")  # %0 fallback

    def test_mom_requires_at_least_5_snapshots(self):
        current = make_snapshot("110000")
        snaps = [make_snapshot(f"{100000 + i * 100}", snapshot_date_offset=i + 1) for i in range(3)]
        result = calculate_changes([current] + snaps)
        assert result.mom_change_tl == Decimal("0")  # 5 snapshot yok

    def test_mom_uses_4_weeks_ago(self):
        current = make_snapshot("130000")
        snaps = [
            make_snapshot("125000", snapshot_date_offset=1),
            make_snapshot("120000", snapshot_date_offset=2),
            make_snapshot("115000", snapshot_date_offset=3),
            make_snapshot("100000", snapshot_date_offset=4),  # snapshots[4] = month_ago
        ]
        result = calculate_changes([current] + snaps)
        assert result.mom_change_tl == Decimal("30000")
        assert result.mom_change_pct == Decimal("30.00")

    def test_changes_preserve_snapshot_date(self):
        current = make_snapshot("100000")
        result = calculate_changes([current])
        assert result.snapshot_date == date(2026, 4, 26)


# ─── calculate_breakdown ──────────────────────────────────────────────────────

class TestCalculateBreakdown:
    def test_breakdown_sums_to_100_percent(self):
        snap = make_snapshot(
            "100000",
            make_position(asset_type="crypto", total_value_tl="40000"),
            make_position(asset_type="staked_crypto", total_value_tl="10000"),
            make_position(asset_type="fund", total_value_tl="30000"),
            make_position(asset_type="pension", total_value_tl="15000"),
            make_position(asset_type="cash", total_value_tl="5000"),
        )
        result = calculate_breakdown(snap)
        total = (
            result.crypto_pct + result.staked_crypto_pct + result.fund_pct +
            result.pension_pct + result.cash_pct
        )
        assert total == Decimal("100.00")

    def test_breakdown_individual_percentages(self):
        snap = make_snapshot(
            "200000",
            make_position(asset_type="crypto", total_value_tl="100000"),
            make_position(asset_type="fund", total_value_tl="50000"),
            make_position(asset_type="pension", total_value_tl="50000"),
        )
        result = calculate_breakdown(snap)
        assert result.crypto_pct == Decimal("50.00")
        assert result.fund_pct == Decimal("25.00")
        assert result.pension_pct == Decimal("25.00")
        assert result.staked_crypto_pct == Decimal("0.00")
        assert result.cash_pct == Decimal("0.00")

    def test_breakdown_handles_zero_total(self):
        snap = make_snapshot("0")
        result = calculate_breakdown(snap)
        # Sıfıra bölme yok; tüm %'ler 0
        assert result.crypto_pct == Decimal("0.00")
        assert result.fund_pct == Decimal("0.00")

    def test_top_assets_sorted_by_value_desc(self):
        snap = make_snapshot(
            "60000",
            make_position(symbol="A", total_value_tl="10000"),
            make_position(symbol="B", total_value_tl="30000"),
            make_position(symbol="C", total_value_tl="20000"),
        )
        result = calculate_breakdown(snap)
        symbols = [a.symbol for a in result.top_assets]
        assert symbols == ["B", "C", "A"]

    def test_top_assets_capped_at_5(self):
        positions = [
            make_position(symbol=f"S{i}", total_value_tl=str(1000 - i * 10))
            for i in range(10)
        ]
        snap = make_snapshot("9550", *positions)
        result = calculate_breakdown(snap)
        assert len(result.top_assets) == 5

    def test_breakdown_aggregates_same_asset_type(self):
        """Aynı asset_type'a sahip birden fazla pozisyon toplanmalı."""
        snap = make_snapshot(
            "100000",
            make_position(asset_type="crypto", symbol="BTC", total_value_tl="40000"),
            make_position(asset_type="crypto", symbol="ETH", total_value_tl="30000"),
            make_position(asset_type="fund", total_value_tl="30000"),
        )
        result = calculate_breakdown(snap)
        assert result.crypto_pct == Decimal("70.00")
        assert result.fund_pct == Decimal("30.00")


# ─── extract_staking_positions ────────────────────────────────────────────────

class TestExtractStakingPositions:
    def test_only_staked_positions_returned(self):
        snap = make_snapshot(
            "0",
            make_position(symbol="BTC", liquid="1.0", staked="0", rewards="0", total_value_tl="0"),
            make_position(symbol="S", liquid="0", staked="100.0", rewards="5.0", unit_price_tl="2", total_value_tl="0"),
        )
        result = extract_staking_positions(snap)
        assert len(result) == 1
        assert result[0].symbol == "S"

    def test_staked_value_calculated(self):
        snap = make_snapshot(
            "0",
            make_position(
                symbol="S",
                provider="sonic",
                staked="100",
                rewards="5",
                unit_price_tl="2.5",
            ),
        )
        result = extract_staking_positions(snap)
        assert result[0].staked_value_tl == Decimal("250.00")
        assert result[0].rewards_value_tl == Decimal("12.50")

    def test_no_staking_returns_empty(self):
        snap = make_snapshot(
            "0",
            make_position(liquid="1.0", staked="0", rewards="0"),
        )
        assert extract_staking_positions(snap) == []

    def test_provider_and_symbol_preserved(self):
        snap = make_snapshot(
            "0",
            make_position(
                symbol="AVAX",
                provider="avalanche_p",
                name="Avalanche P-Chain",
                staked="50",
                unit_price_tl="100",
            ),
        )
        result = extract_staking_positions(snap)
        assert result[0].provider == "avalanche_p"
        assert result[0].symbol == "AVAX"
        assert result[0].name == "Avalanche P-Chain"


# ─── to_asset_position ────────────────────────────────────────────────────────

class TestToAssetPosition:
    def _asset(self, **kw):
        defaults = dict(
            source_type="exchange",
            provider="binance",
            asset_type="crypto",
            symbol="BTC",
            name="Bitcoin",
            liquid_quantity=Decimal("0"),
            staked_quantity=Decimal("0"),
            pending_rewards=Decimal("0"),
            unit_price_usd=Decimal("0"),
            unit_price_tl=Decimal("0"),
            wallet_address_id=None,
        )
        defaults.update(kw)
        return AssetData(**defaults)

    def test_uses_unit_price_tl_when_available(self):
        asset = self._asset(unit_price_tl=Decimal("50"), unit_price_usd=Decimal("999"))
        pos = to_asset_position(asset, snapshot_id=None, usd_tl_rate=Decimal("33"), total_value_tl=Decimal("1000"))
        # unit_price_tl > 0 ise USD * kur'a değil direkt TL'ye düşmeli
        assert pos.unit_price_tl == Decimal("50")

    def test_falls_back_to_usd_times_rate(self):
        asset = self._asset(unit_price_tl=Decimal("0"), unit_price_usd=Decimal("100"))
        pos = to_asset_position(asset, snapshot_id=None, usd_tl_rate=Decimal("33"), total_value_tl=Decimal("3300"))
        assert pos.unit_price_tl == Decimal("3300")

    def test_total_value_tl_uses_all_quantities(self):
        asset = self._asset(
            liquid_quantity=Decimal("1"),
            staked_quantity=Decimal("2"),
            pending_rewards=Decimal("0.5"),
            unit_price_tl=Decimal("100"),
        )
        pos = to_asset_position(asset, snapshot_id=None, usd_tl_rate=Decimal("33"), total_value_tl=Decimal("350"))
        # (1 + 2 + 0.5) * 100 = 350
        assert pos.total_value_tl == Decimal("350")

    def test_weight_pct_calculated(self):
        asset = self._asset(
            liquid_quantity=Decimal("1"),
            unit_price_tl=Decimal("250"),
        )
        pos = to_asset_position(asset, snapshot_id=None, usd_tl_rate=Decimal("33"), total_value_tl=Decimal("1000"))
        assert pos.weight_pct == Decimal("25.00")

    def test_weight_pct_zero_total_does_not_crash(self):
        asset = self._asset(unit_price_tl=Decimal("100"), liquid_quantity=Decimal("1"))
        pos = to_asset_position(asset, snapshot_id=None, usd_tl_rate=Decimal("33"), total_value_tl=Decimal("0"))
        assert pos.weight_pct == Decimal("0.00")
