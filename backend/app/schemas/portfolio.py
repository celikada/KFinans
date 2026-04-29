from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class AssetPositionOut(BaseModel):
    id: str
    source_type: str
    provider: str
    asset_type: str
    symbol: str
    name: str
    liquid_quantity: Decimal
    staked_quantity: Decimal
    pending_rewards: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
    weight_pct: Decimal

    class Config:
        from_attributes = True


class SnapshotOut(BaseModel):
    id: str
    snapshot_date: date
    total_value_tl: Decimal
    asset_positions: list[AssetPositionOut] = []

    class Config:
        from_attributes = True


class PortfolioChanges(BaseModel):
    current_value_tl: Decimal
    wow_change_tl: Decimal
    wow_change_pct: Decimal
    mom_change_tl: Decimal
    mom_change_pct: Decimal
    snapshot_date: date


class PortfolioBreakdown(BaseModel):
    crypto_pct: Decimal
    staked_crypto_pct: Decimal
    fund_pct: Decimal
    pension_pct: Decimal
    cash_pct: Decimal
    top_assets: list[AssetPositionOut]


class StakingPosition(BaseModel):
    provider: str
    symbol: str
    name: str
    staked_quantity: Decimal
    pending_rewards: Decimal
    staked_value_tl: Decimal
    rewards_value_tl: Decimal


class CryptoPositionOut(BaseModel):
    provider: str
    symbol: str
    liquid_quantity: Decimal
    staked_quantity: Decimal
    unit_price_usd: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal


class CryptoResponse(BaseModel):
    positions: list[CryptoPositionOut]
    errors: dict[str, str]


class WalletPositionOut(BaseModel):
    wallet_id: str
    chain: str
    address: str
    label: str | None
    symbol: str
    liquid_quantity: Decimal
    staked_quantity: Decimal
    pending_rewards: Decimal
    unit_price_usd: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal


class WalletResponse(BaseModel):
    positions: list[WalletPositionOut]
    errors: dict[str, str]
