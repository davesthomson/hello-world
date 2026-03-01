"""Dataclasses representing database models."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class Account:
    id: Optional[int] = None
    name: str = ""
    account_number: Optional[str] = None
    broker: str = "ibkr"
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Position:
    id: Optional[int] = None
    account_id: Optional[int] = None
    ticker: str = ""
    name: Optional[str] = None
    quantity: float = 0.0
    avg_cost_basis: Optional[float] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    asset_type: str = "stock"
    sector: Optional[str] = None
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Trade:
    id: Optional[int] = None
    account_id: Optional[int] = None
    ticker: str = ""
    side: str = "buy"
    quantity: float = 0.0
    price: float = 0.0
    fees: float = 0.0
    trade_date: Optional[datetime] = None
    notes: Optional[str] = None
    source: str = "ibkr_sync"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PortfolioSnapshot:
    id: Optional[int] = None
    account_id: Optional[int] = None
    date: Optional[date] = None
    total_value: Optional[float] = None
    cash_balance: Optional[float] = None
    invested_value: Optional[float] = None
    created_at: Optional[datetime] = None


@dataclass
class PriceCache:
    ticker: str = ""
    date: Optional[date] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adjusted_close: Optional[float] = None
    volume: Optional[int] = None


@dataclass
class WatchlistItem:
    id: Optional[int] = None
    ticker: str = ""
    notes: Optional[str] = None
    added_date: Optional[datetime] = None
