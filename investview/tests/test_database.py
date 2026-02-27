"""Tests for database operations."""

import sys
from pathlib import Path

# Ensure investview package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from db.database import (
    get_connection,
    init_db,
    reset_db,
    insert_account,
    get_accounts,
    upsert_positions,
    get_positions,
    insert_trades,
    get_trades,
    upsert_snapshot,
    get_snapshots,
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()


class TestAccounts:
    def test_insert_and_get(self, db):
        acct_id = insert_account(db, "Test Account", "ibkr", "****1234")
        assert acct_id is not None
        assert acct_id > 0

        accounts = get_accounts(db)
        assert len(accounts) == 1
        assert accounts[0]["name"] == "Test Account"
        assert accounts[0]["broker"] == "ibkr"
        assert accounts[0]["account_number"] == "****1234"
        assert accounts[0]["is_active"] == 1

    def test_multiple_accounts(self, db):
        insert_account(db, "IBKR Main", "ibkr")
        insert_account(db, "E*Trade Roth", "etrade")
        insert_account(db, "CSV Import", "csv_import")

        accounts = get_accounts(db)
        assert len(accounts) == 3

    def test_inactive_account_filtered(self, db):
        insert_account(db, "Active", "ibkr", is_active=True)
        acct2 = insert_account(db, "Inactive", "etrade", is_active=False)

        active = get_accounts(db, active_only=True)
        assert len(active) == 1
        assert active[0]["name"] == "Active"

        all_accts = get_accounts(db, active_only=False)
        assert len(all_accts) == 2


class TestPositions:
    def test_upsert_and_get(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        positions = [
            {
                "ticker": "AAPL",
                "quantity": 100,
                "avg_cost_basis": 150.0,
                "current_price": 175.0,
                "market_value": 17500.0,
                "unrealized_pnl": 2500.0,
                "unrealized_pnl_pct": 16.67,
                "asset_type": "stock",
            },
            {
                "ticker": "SPY",
                "quantity": 50,
                "avg_cost_basis": 420.0,
                "current_price": 450.0,
                "market_value": 22500.0,
                "unrealized_pnl": 1500.0,
                "unrealized_pnl_pct": 7.14,
                "asset_type": "etf",
            },
        ]
        count = upsert_positions(db, acct_id, positions)
        assert count == 2

        result = get_positions(db, account_id=acct_id)
        assert len(result) == 2

    def test_upsert_replaces_old(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        upsert_positions(db, acct_id, [
            {"ticker": "AAPL", "quantity": 100, "current_price": 150, "market_value": 15000, "asset_type": "stock"},
        ])
        assert len(get_positions(db, account_id=acct_id)) == 1

        # Upsert with new positions replaces old
        upsert_positions(db, acct_id, [
            {"ticker": "MSFT", "quantity": 50, "current_price": 300, "market_value": 15000, "asset_type": "stock"},
            {"ticker": "GOOG", "quantity": 25, "current_price": 140, "market_value": 3500, "asset_type": "stock"},
        ])
        result = get_positions(db, account_id=acct_id)
        assert len(result) == 2
        tickers = {r["ticker"] for r in result}
        assert tickers == {"MSFT", "GOOG"}

    def test_filter_by_asset_type(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        upsert_positions(db, acct_id, [
            {"ticker": "AAPL", "quantity": 100, "market_value": 15000, "asset_type": "stock"},
            {"ticker": "SPY", "quantity": 50, "market_value": 22500, "asset_type": "etf"},
        ])
        stocks = get_positions(db, asset_type="stock")
        assert len(stocks) == 1
        assert stocks[0]["ticker"] == "AAPL"


class TestTrades:
    def test_insert_and_get(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        trades = [
            {
                "account_id": acct_id,
                "ticker": "AAPL",
                "side": "buy",
                "quantity": 100,
                "price": 150.0,
                "fees": 1.0,
                "trade_date": "2024-01-15T10:30:00",
                "notes": "Initial purchase",
                "source": "manual",
            },
        ]
        count = insert_trades(db, trades)
        assert count == 1

        result = get_trades(db, account_id=acct_id)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["side"] == "buy"
        assert result[0]["quantity"] == 100

    def test_filter_by_ticker(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        insert_trades(db, [
            {"account_id": acct_id, "ticker": "AAPL", "side": "buy", "quantity": 10, "price": 150, "trade_date": "2024-01-01"},
            {"account_id": acct_id, "ticker": "MSFT", "side": "buy", "quantity": 20, "price": 300, "trade_date": "2024-01-02"},
        ])
        result = get_trades(db, ticker="AAPL")
        assert len(result) == 1

    def test_filter_by_date_range(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        insert_trades(db, [
            {"account_id": acct_id, "ticker": "AAPL", "side": "buy", "quantity": 10, "price": 150, "trade_date": "2024-01-01"},
            {"account_id": acct_id, "ticker": "AAPL", "side": "buy", "quantity": 20, "price": 155, "trade_date": "2024-06-15"},
            {"account_id": acct_id, "ticker": "AAPL", "side": "sell", "quantity": 5, "price": 170, "trade_date": "2024-12-01"},
        ])
        result = get_trades(db, start_date="2024-06-01", end_date="2024-07-01")
        assert len(result) == 1
        assert result[0]["quantity"] == 20


class TestSnapshots:
    def test_upsert_and_get(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        upsert_snapshot(db, acct_id, "2024-01-15", 100000.0, 20000.0, 80000.0)
        upsert_snapshot(db, acct_id, "2024-01-16", 101000.0, 19500.0, 81500.0)

        snaps = get_snapshots(db, account_id=acct_id)
        assert len(snaps) == 2
        assert snaps[0]["total_value"] == 100000.0
        assert snaps[1]["total_value"] == 101000.0

    def test_upsert_updates_existing(self, db):
        acct_id = insert_account(db, "Test", "ibkr")
        upsert_snapshot(db, acct_id, "2024-01-15", 100000.0)
        upsert_snapshot(db, acct_id, "2024-01-15", 105000.0)  # same date

        snaps = get_snapshots(db, account_id=acct_id)
        assert len(snaps) == 1
        assert snaps[0]["total_value"] == 105000.0

    def test_aggregate_snapshot(self, db):
        upsert_snapshot(db, None, "2024-01-15", 250000.0)
        snaps = get_snapshots(db, account_id=None)
        assert len(snaps) == 1


class TestWatchlist:
    def test_add_and_get(self, db):
        add_to_watchlist(db, "AAPL", "Core holding")
        add_to_watchlist(db, "MSFT")

        items = get_watchlist(db)
        assert len(items) == 2
        tickers = {i["ticker"] for i in items}
        assert tickers == {"AAPL", "MSFT"}

    def test_duplicate_ignored(self, db):
        add_to_watchlist(db, "AAPL")
        add_to_watchlist(db, "AAPL")  # should not raise

        items = get_watchlist(db)
        assert len(items) == 1

    def test_remove(self, db):
        add_to_watchlist(db, "AAPL")
        add_to_watchlist(db, "MSFT")
        remove_from_watchlist(db, "AAPL")

        items = get_watchlist(db)
        assert len(items) == 1
        assert items[0]["ticker"] == "MSFT"

    def test_case_normalized(self, db):
        add_to_watchlist(db, "aapl")
        items = get_watchlist(db)
        assert items[0]["ticker"] == "AAPL"


class TestResetDB:
    def test_reset_clears_data(self, db):
        insert_account(db, "Test", "ibkr")
        assert len(get_accounts(db)) == 1

        reset_db(db)
        assert len(get_accounts(db)) == 0
