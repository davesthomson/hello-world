"""FRED macroeconomic data wrapper using fredapi."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import FRED_API_KEY

logger = logging.getLogger(__name__)

# Lazy-initialised FRED client
_fred = None


def _get_fred():
    """Return a Fred client, or None if the API key is missing."""
    global _fred
    if _fred is not None:
        return _fred
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — macro data unavailable")
        return None
    from fredapi import Fred
    _fred = Fred(api_key=FRED_API_KEY)
    return _fred


def is_available() -> bool:
    """Return True if FRED data can be fetched."""
    return _get_fred() is not None


def get_fed_funds_rate() -> Optional[float]:
    """Current effective federal funds rate (daily series DFF)."""
    try:
        fred = _get_fred()
        if fred is None:
            return None
        data = fred.get_series("DFF")
        return float(data.dropna().iloc[-1])
    except Exception as exc:
        logger.warning("Failed to get fed funds rate: %s", exc)
        return None


def get_treasury_yields() -> dict[str, Optional[float]]:
    """Return latest Treasury yields keyed by maturity label."""
    series_map = {
        "2Y": "DGS2",
        "5Y": "DGS5",
        "10Y": "DGS10",
        "30Y": "DGS30",
    }
    result: dict[str, Optional[float]] = {}
    fred = _get_fred()
    if fred is None:
        return {k: None for k in series_map}
    for label, series_id in series_map.items():
        try:
            data = fred.get_series(series_id)
            val = data.dropna().iloc[-1]
            result[label] = float(val)
        except Exception as exc:
            logger.warning("Failed to get %s yield: %s", label, exc)
            result[label] = None
    return result


def get_yield_curve() -> pd.DataFrame:
    """Return a DataFrame with the full yield curve for plotting.

    Columns: maturity (str), yield (float).
    """
    maturities = {
        "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
        "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3",
        "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10",
        "20Y": "DGS20", "30Y": "DGS30",
    }
    fred = _get_fred()
    rows = []
    for label, series_id in maturities.items():
        val = None
        if fred:
            try:
                data = fred.get_series(series_id)
                val = float(data.dropna().iloc[-1])
            except Exception:
                pass
        rows.append({"maturity": label, "yield": val})
    return pd.DataFrame(rows)


def get_cpi() -> dict:
    """Return latest CPI reading and YoY change.

    Keys: latest, yoy_change (percentage).
    """
    result: dict = {"latest": None, "yoy_change": None}
    fred = _get_fred()
    if fred is None:
        return result
    try:
        data = fred.get_series("CPIAUCSL")
        data = data.dropna()
        result["latest"] = float(data.iloc[-1])
        if len(data) >= 13:
            year_ago = float(data.iloc[-13])
            result["yoy_change"] = ((result["latest"] - year_ago) / year_ago) * 100
    except Exception as exc:
        logger.warning("Failed to get CPI: %s", exc)
    return result


def get_unemployment() -> Optional[float]:
    """Latest unemployment rate."""
    try:
        fred = _get_fred()
        if fred is None:
            return None
        data = fred.get_series("UNRATE")
        return float(data.dropna().iloc[-1])
    except Exception as exc:
        logger.warning("Failed to get unemployment rate: %s", exc)
        return None


def get_series(series_id: str, start_date: str | None = None,
               end_date: str | None = None) -> pd.Series:
    """Generic FRED series fetch."""
    fred = _get_fred()
    if fred is None:
        return pd.Series(dtype=float)
    try:
        kwargs = {}
        if start_date:
            kwargs["observation_start"] = start_date
        if end_date:
            kwargs["observation_end"] = end_date
        return fred.get_series(series_id, **kwargs)
    except Exception as exc:
        logger.warning("Failed to get FRED series %s: %s", series_id, exc)
        return pd.Series(dtype=float)
