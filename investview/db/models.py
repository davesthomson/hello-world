"""Dataclass models for InvestView entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Account:
    id: int = 0
    name: str = ""
    broker: str = ""
    account_number: str = ""
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Position:
    id: int = 0
    account_id: int = 0
    ticker: str = ""
    quantity: float = 0.0
    avg_cost_basis: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    asset_type: str = "stock"
    last_updated: datetime | None = None
    # Joined fields
    account_name: str = ""
    broker: str = ""


@dataclass
class Trade:
    id: int = 0
    account_id: int = 0
    ticker: str = ""
    side: str = "buy"
    quantity: float = 0.0
    price: float = 0.0
    fees: float = 0.0
    trade_date: datetime | None = None
    notes: str = ""
    source: str = "manual"
    # Joined fields
    account_name: str = ""


@dataclass
class PortfolioSnapshot:
    id: int = 0
    account_id: int | None = None
    date: date | None = None
    total_value: float = 0.0
    cash_balance: float = 0.0
    invested_value: float = 0.0


@dataclass
class WatchlistItem:
    id: int = 0
    ticker: str = ""
    added_date: datetime | None = None
    notes: str = ""


@dataclass
class PriceCacheEntry:
    ticker: str = ""
    date: date | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    adjusted_close: float | None = None


@dataclass
class AccountSummary:
    """Summary data returned by broker adapters."""
    total_value: float = 0.0
    cash_balance: float = 0.0
    buying_power: float = 0.0
    invested_value: float = 0.0
    day_pnl: float = 0.0
    day_pnl_pct: float = 0.0
    positions_count: int = 0
