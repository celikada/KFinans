from decimal import Decimal
import httpx
from app.services.base import AssetData
from app.models.portfolio import PortfolioSnapshot, AssetPosition
from app.schemas.portfolio import PortfolioChanges, PortfolioBreakdown, StakingPosition

TCMB_RATE_URL = "https://api.exchangerate-api.com/v4/latest/USD"


async def fetch_usd_to_tl() -> Decimal:
    """Anlık USD/TL kurunu çeker."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(TCMB_RATE_URL)
        data = resp.json()
        return Decimal(str(data["rates"]["TRY"]))


def to_asset_position(asset: AssetData, snapshot_id, usd_tl_rate: Decimal, total_value_tl: Decimal) -> AssetPosition:
    if asset.unit_price_tl > 0:
        price_tl = asset.unit_price_tl
    else:
        price_tl = asset.unit_price_usd * usd_tl_rate

    total_qty = asset.liquid_quantity + asset.staked_quantity + asset.pending_rewards
    value_tl = total_qty * price_tl
    weight = (value_tl / total_value_tl * 100) if total_value_tl > 0 else Decimal(0)

    return AssetPosition(
        snapshot_id=snapshot_id,
        source_type=asset.source_type,
        provider=asset.provider,
        asset_type=asset.asset_type,
        symbol=asset.symbol,
        name=asset.name,
        liquid_quantity=asset.liquid_quantity,
        staked_quantity=asset.staked_quantity,
        pending_rewards=asset.pending_rewards,
        unit_price_tl=price_tl,
        total_value_tl=value_tl,
        weight_pct=weight.quantize(Decimal("0.01")),
        wallet_address_id=asset.wallet_address_id,
    )


def calculate_changes(snapshots: list[PortfolioSnapshot]) -> PortfolioChanges:
    current = snapshots[0]
    wow_change_tl = Decimal(0)
    wow_change_pct = Decimal(0)
    mom_change_tl = Decimal(0)
    mom_change_pct = Decimal(0)

    if len(snapshots) >= 2:
        prev_week = snapshots[1]
        wow_change_tl = current.total_value_tl - prev_week.total_value_tl
        wow_change_pct = (wow_change_tl / prev_week.total_value_tl * 100) if prev_week.total_value_tl else Decimal(0)

    if len(snapshots) >= 5:
        prev_month = snapshots[4]
        mom_change_tl = current.total_value_tl - prev_month.total_value_tl
        mom_change_pct = (mom_change_tl / prev_month.total_value_tl * 100) if prev_month.total_value_tl else Decimal(0)

    return PortfolioChanges(
        current_value_tl=current.total_value_tl,
        wow_change_tl=wow_change_tl,
        wow_change_pct=wow_change_pct.quantize(Decimal("0.01")),
        mom_change_tl=mom_change_tl,
        mom_change_pct=mom_change_pct.quantize(Decimal("0.01")),
        snapshot_date=current.snapshot_date,
    )


def calculate_breakdown(snapshot: PortfolioSnapshot) -> PortfolioBreakdown:
    totals = {"crypto": Decimal(0), "staked_crypto": Decimal(0), "fund": Decimal(0), "pension": Decimal(0), "cash": Decimal(0)}
    for pos in snapshot.asset_positions:
        totals[pos.asset_type] = totals.get(pos.asset_type, Decimal(0)) + pos.total_value_tl

    total = snapshot.total_value_tl or Decimal(1)
    pct = lambda v: (v / total * 100).quantize(Decimal("0.01"))

    top_assets = sorted(snapshot.asset_positions, key=lambda p: p.total_value_tl, reverse=True)[:5]

    return PortfolioBreakdown(
        crypto_pct=pct(totals["crypto"]),
        staked_crypto_pct=pct(totals["staked_crypto"]),
        fund_pct=pct(totals["fund"]),
        pension_pct=pct(totals["pension"]),
        cash_pct=pct(totals["cash"]),
        top_assets=top_assets,
    )


def extract_staking_positions(snapshot: PortfolioSnapshot) -> list[StakingPosition]:
    return [
        StakingPosition(
            provider=pos.provider,
            symbol=pos.symbol,
            name=pos.name,
            staked_quantity=pos.staked_quantity,
            pending_rewards=pos.pending_rewards,
            staked_value_tl=(pos.staked_quantity * pos.unit_price_tl).quantize(Decimal("0.01")),
            rewards_value_tl=(pos.pending_rewards * pos.unit_price_tl).quantize(Decimal("0.01")),
        )
        for pos in snapshot.asset_positions
        if pos.staked_quantity > 0
    ]
