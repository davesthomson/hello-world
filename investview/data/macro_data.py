"""FRED API wrapper for macroeconomic data."""

from __future__ import annotations

from datetime import datetime, timedelta

from config import FRED_API_KEY, logger

# Common FRED series IDs
SERIES_FED_FUNDS = "FEDFUNDS"
SERIES_10Y_TREASURY = "DGS10"
SERIES_2Y_TREASURY = "DGS2"
SERIES_CPI = "CPIAUCSL"
SERIES_CPI_YOY = "CPIAUCNS"


def _get_fred():
    """Return a FRED client, or None if not configured."""
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not configured — macro data unavailable")
        return None
    try:
        from fredapi import Fred
        return Fred(api_key=FRED_API_KEY)
    except Exception as e:
        logger.error("Failed to initialize FRED client: %s", e)
        return None


def get_series(
    series_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Fetch a generic FRED series. Returns a pandas Series or None."""
    fred = _get_fred()
    if fred is None:
        return None
    try:
        kwargs = {}
        if start_date:
            kwargs["observation_start"] = start_date
        if end_date:
            kwargs["observation_end"] = end_date
        return fred.get_series(series_id, **kwargs)
    except Exception as e:
        logger.warning("Failed to fetch FRED series %s: %s", series_id, e)
        return None


def get_fed_funds_rate() -> float | None:
    """Get the most recent Federal Funds effective rate."""
    data = get_series(SERIES_FED_FUNDS)
    if data is not None and not data.empty:
        return float(data.iloc[-1])
    return None


def get_treasury_yields(maturity: str = "10y") -> float | None:
    """Get the latest Treasury yield for a given maturity.

    Args:
        maturity: '2y' or '10y'.
    """
    series_map = {
        "2y": SERIES_2Y_TREASURY,
        "10y": SERIES_10Y_TREASURY,
    }
    series_id = series_map.get(maturity)
    if not series_id:
        logger.warning("Unsupported maturity: %s", maturity)
        return None

    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    data = get_series(series_id, start_date=start)
    if data is not None and not data.empty:
        # FRED data may have NaN for weekends/holidays; get last valid
        valid = data.dropna()
        if not valid.empty:
            return float(valid.iloc[-1])
    return None


def get_cpi() -> dict | None:
    """Get recent CPI data.

    Returns dict with 'latest' (index value) and 'yoy_change' (% change).
    """
    start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    data = get_series(SERIES_CPI, start_date=start)
    if data is None or data.empty:
        return None

    valid = data.dropna()
    if len(valid) < 13:
        return {"latest": float(valid.iloc[-1]), "yoy_change": None}

    latest = float(valid.iloc[-1])
    year_ago = float(valid.iloc[-13])  # ~12 months prior
    yoy = ((latest - year_ago) / year_ago) * 100

    return {"latest": latest, "yoy_change": round(yoy, 2)}
