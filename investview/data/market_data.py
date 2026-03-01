"""Market data wrapper around yfinance with caching."""

from __future__ import annotations

import sqlite3
import time
from datetime import date, datetime, timedelta

import pandas as pd

from config import logger

# Period/interval mapping for yfinance
VALID_PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max")
VALID_INTERVALS = ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")


def get_current_price(ticker: str) -> float | None:
    """Get the latest price for a ticker via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            price = getattr(info, "previous_close", None)
        return float(price) if price else None
    except Exception as e:
        logger.warning("Failed to get current price for %s: %s", ticker, e)
        return None


def get_price_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Get historical price data, checking cache first.

    Args:
        ticker: Stock ticker symbol.
        period: yfinance period string.
        interval: yfinance interval string.
        conn: Optional DB connection for caching.

    Returns:
        DataFrame with OHLCV data.
    """
    try:
        import yfinance as yf
        from data.cache import cache_prices

        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)

        if df.empty:
            logger.warning("No price history returned for %s", ticker)
            return pd.DataFrame()

        # Cache daily data
        if conn is not None and interval == "1d":
            cache_prices(conn, ticker, df)

        return df
    except Exception as e:
        logger.warning("Failed to get price history for %s: %s", ticker, e)
        return pd.DataFrame()


def get_ticker_info(ticker: str) -> dict:
    """Get company info for a ticker (name, sector, market cap, etc.)."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "name": info.get("shortName", info.get("longName", ticker)),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "beta": info.get("beta"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", ""),
        }
    except Exception as e:
        logger.warning("Failed to get ticker info for %s: %s", ticker, e)
        return {"name": ticker, "sector": "N/A"}


def get_multiple_prices(tickers: list[str], max_retries: int = 3) -> dict[str, float | None]:
    """Get current prices for multiple tickers at once.

    Retries with exponential backoff on failure (e.g. Yahoo 429 rate limits).
    """
    import yfinance as yf

    prices: dict[str, float | None] = {}

    for attempt in range(max_retries):
        try:
            data = yf.download(tickers, period="5d", progress=False, threads=True)
            if data.empty:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.info("yf.download returned empty, retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                return {t: None for t in tickers}

            # yf.download returns MultiIndex columns for multiple tickers
            if len(tickers) == 1:
                close = data.get("Close")
                if close is not None and not close.empty:
                    prices[tickers[0]] = float(close.iloc[-1])
                else:
                    prices[tickers[0]] = None
            else:
                close_data = data.get("Close")
                if close_data is not None:
                    for t in tickers:
                        try:
                            val = close_data[t].dropna()
                            prices[t] = float(val.iloc[-1]) if not val.empty else None
                        except (KeyError, IndexError):
                            prices[t] = None
            break  # success
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("yf.download failed (attempt %d/%d), retrying in %ds: %s", attempt + 1, max_retries, wait, e)
                time.sleep(wait)
            else:
                logger.warning("yf.download failed after %d attempts: %s", max_retries, e)
                prices = {t: None for t in tickers}

    # Fill in any missing
    for t in tickers:
        if t not in prices:
            prices[t] = None
    return prices
