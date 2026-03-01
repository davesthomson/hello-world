"""Market data wrapper around yfinance with SQLite caching."""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from db.database import get_cached_prices, save_price_cache

logger = logging.getLogger(__name__)


def get_current_price(ticker: str) -> Optional[float]:
    """Fetch the latest price for a single ticker.

    Returns None on failure.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            # Fallback: latest close from history
            hist = t.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return float(price) if price else None
    except Exception as exc:
        logger.warning("Failed to get price for %s: %s", ticker, exc)
        return None


def get_price_history(ticker: str, period: str = "1y",
                      interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV DataFrame for *ticker*.

    Checks the price_cache first for daily data, then fetches from
    yfinance and stores new rows in the cache.
    """
    try:
        # For intraday intervals, skip cache
        if interval != "1d":
            df = yf.Ticker(ticker).history(period=period, interval=interval)
            return _normalise_df(df)

        # Determine date range from period string
        end_date = date.today()
        start_date = _period_to_start(period, end_date)

        # Check cache
        cached = get_cached_prices(
            ticker, start_date.isoformat(), end_date.isoformat()
        )
        cached_dates = {row["date"] for row in cached}

        # Fetch from yfinance
        df = yf.Ticker(ticker).history(
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            interval="1d",
        )
        if df.empty:
            # Fall back to whatever we had in cache
            if cached:
                return pd.DataFrame(cached).set_index("date")
            return pd.DataFrame()

        df = _normalise_df(df)

        # Store new rows in cache
        new_rows = []
        for idx, row in df.iterrows():
            d = str(idx)[:10]
            if d not in cached_dates:
                new_rows.append({
                    "date": d,
                    "open": row.get("Open"),
                    "high": row.get("High"),
                    "low": row.get("Low"),
                    "close": row.get("Close"),
                    "adjusted_close": row.get("Close"),
                    "volume": int(row.get("Volume", 0)),
                })
        if new_rows:
            save_price_cache(ticker, new_rows)
            logger.info("Cached %d new price rows for %s", len(new_rows), ticker)

        return df

    except Exception as exc:
        logger.warning("Failed to get price history for %s: %s", ticker, exc)
        return pd.DataFrame()


def get_ticker_info(ticker: str) -> dict:
    """Return company info dict for *ticker*.

    Keys: name, sector, market_cap, pe_ratio, dividend_yield,
          fifty_two_week_high, fifty_two_week_low, avg_volume.
    """
    result: dict = {}
    try:
        info = yf.Ticker(ticker).info
        result = {
            "name": info.get("shortName") or info.get("longName", ""),
            "sector": info.get("sector", ""),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
        }
    except Exception as exc:
        logger.warning("Failed to get info for %s: %s", ticker, exc)
    return result


def get_multiple_prices(tickers: list[str]) -> dict[str, Optional[float]]:
    """Batch-fetch current prices for a list of tickers."""
    prices: dict[str, Optional[float]] = {}
    for t in tickers:
        prices[t] = get_current_price(t)
    return prices


def calculate_moving_averages(df: pd.DataFrame,
                              windows: list[int] | None = None) -> pd.DataFrame:
    """Add moving-average columns to a price DataFrame.

    E.g. windows=[50, 200] adds columns ``MA_50`` and ``MA_200``.
    """
    if windows is None:
        windows = [50, 200]
    df = df.copy()
    for w in windows:
        col = f"MA_{w}"
        df[col] = df["Close"].rolling(window=w).mean()
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the DataFrame index is a simple date string."""
    if df.index.name != "Date":
        df.index.name = "Date"
    df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
    return df


def _period_to_start(period: str, end: date) -> date:
    """Convert a yfinance-style period string to a start date."""
    mapping = {
        "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
        "6mo": 180, "1y": 365, "2y": 730, "5y": 1825,
        "10y": 3650, "max": 36500, "ytd": None,
    }
    if period == "ytd":
        return date(end.year, 1, 1)
    days = mapping.get(period, 365)
    return end - timedelta(days=days)
