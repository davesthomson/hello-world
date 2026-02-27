"""Simple write-through price cache backed by the price_cache SQLite table."""

from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd

from config import logger


def get_cached_price(conn: sqlite3.Connection, ticker: str, dt: date) -> dict | None:
    """Return a cached price row for a ticker on a specific date, or None."""
    # Skip cache for today — always fetch fresh
    if dt == date.today():
        return None

    row = conn.execute(
        "SELECT * FROM price_cache WHERE ticker = ? AND date = ?",
        (ticker.upper(), dt.isoformat()),
    ).fetchone()
    if row:
        return dict(row)
    return None


def get_cached_history(
    conn: sqlite3.Connection, ticker: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """Return cached price history for a ticker within a date range."""
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume, adjusted_close
           FROM price_cache
           WHERE ticker = ? AND date >= ? AND date <= ?
           ORDER BY date ASC""",
        (ticker.upper(), start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def cache_prices(conn: sqlite3.Connection, ticker: str, df: pd.DataFrame) -> int:
    """Bulk insert price data from a yfinance-style DataFrame into cache.

    Returns the number of rows cached.
    """
    if df.empty:
        return 0

    ticker = ticker.upper()
    count = 0
    for idx, row in df.iterrows():
        dt = idx
        if hasattr(dt, "date"):
            dt = dt.date()
        dt_str = str(dt)

        try:
            conn.execute(
                """INSERT OR REPLACE INTO price_cache
                   (ticker, date, open, high, low, close, volume, adjusted_close)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker,
                    dt_str,
                    _safe_float(row, "Open"),
                    _safe_float(row, "High"),
                    _safe_float(row, "Low"),
                    _safe_float(row, "Close"),
                    int(row.get("Volume", 0)) if pd.notna(row.get("Volume")) else 0,
                    _safe_float(row, "Adj Close") or _safe_float(row, "Close"),
                ),
            )
            count += 1
        except Exception as e:
            logger.warning("Failed to cache price for %s on %s: %s", ticker, dt_str, e)

    conn.commit()
    logger.info("Cached %d price rows for %s", count, ticker)
    return count


def _safe_float(row: pd.Series, col: str) -> float | None:
    """Safely extract a float from a pandas row."""
    val = row.get(col)
    if val is not None and pd.notna(val):
        return float(val)
    return None
