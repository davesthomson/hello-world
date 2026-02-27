"""Tests for market data layer (cache focused — no live API calls)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from datetime import date, timedelta

from db.database import get_connection, init_db
from data.cache import get_cached_price, cache_prices, get_cached_history


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()


class TestPriceCache:
    def test_cache_and_retrieve(self, db):
        """Test writing prices to cache and reading them back."""
        # Build a small DataFrame mimicking yfinance output
        dates = pd.date_range("2024-01-02", periods=5, freq="B")
        df = pd.DataFrame(
            {
                "Open": [150.0, 151.0, 152.0, 153.0, 154.0],
                "High": [155.0, 156.0, 157.0, 158.0, 159.0],
                "Low": [148.0, 149.0, 150.0, 151.0, 152.0],
                "Close": [153.0, 154.0, 155.0, 156.0, 157.0],
                "Volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            },
            index=dates,
        )
        count = cache_prices(db, "AAPL", df)
        assert count == 5

        # Retrieve a single cached price
        cached = get_cached_price(db, "AAPL", date(2024, 1, 2))
        assert cached is not None
        assert cached["close"] == 153.0
        assert cached["volume"] == 1000000

    def test_cache_miss(self, db):
        """Uncached ticker/date returns None."""
        result = get_cached_price(db, "MSFT", date(2024, 1, 2))
        assert result is None

    def test_cache_skips_today(self, db):
        """Today's date should always return None (force fresh fetch)."""
        today = date.today()
        dates = pd.date_range(today, periods=1)
        df = pd.DataFrame(
            {"Open": [100], "High": [105], "Low": [99], "Close": [103], "Volume": [500000]},
            index=dates,
        )
        cache_prices(db, "TEST", df)

        result = get_cached_price(db, "TEST", today)
        assert result is None  # should skip cache for today

    def test_cached_history(self, db):
        """Test range query for cached history."""
        dates = pd.date_range("2024-01-02", periods=10, freq="B")
        df = pd.DataFrame(
            {
                "Open": range(10),
                "High": range(10, 20),
                "Low": range(10),
                "Close": range(1, 11),
                "Volume": [100] * 10,
            },
            index=dates,
        )
        cache_prices(db, "SPY", df)

        hist = get_cached_history(db, "SPY", date(2024, 1, 2), date(2024, 1, 8))
        assert not hist.empty
        assert len(hist) == 5  # 5 business days in Jan 2-8 inclusive

    def test_case_insensitive_ticker(self, db):
        """Cache should normalize tickers to uppercase."""
        dates = pd.date_range("2024-06-01", periods=1)
        df = pd.DataFrame(
            {"Open": [100], "High": [105], "Low": [99], "Close": [103], "Volume": [500000]},
            index=dates,
        )
        cache_prices(db, "aapl", df)

        cached = get_cached_price(db, "AAPL", date(2024, 6, 1))
        assert cached is not None
        assert cached["close"] == 103

    def test_cache_replaces_on_conflict(self, db):
        """Inserting the same ticker+date again should update."""
        dates = pd.date_range("2024-01-02", periods=1)
        df1 = pd.DataFrame(
            {"Open": [100], "High": [105], "Low": [99], "Close": [103], "Volume": [500]},
            index=dates,
        )
        df2 = pd.DataFrame(
            {"Open": [110], "High": [115], "Low": [109], "Close": [113], "Volume": [600]},
            index=dates,
        )
        cache_prices(db, "AAPL", df1)
        cache_prices(db, "AAPL", df2)

        cached = get_cached_price(db, "AAPL", date(2024, 1, 2))
        assert cached["close"] == 113
