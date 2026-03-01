"""Database connection, table creation, and query helpers."""

import sqlite3
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

# Module-level connection singleton
_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    """Get or create the SQLite database connection."""
    global _connection
    if _connection is None:
        # Ensure the directory for the DB file exists
        db_dir = os.path.dirname(DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        logger.info("Database connection opened: %s", DB_PATH)
    return _connection


def init_db() -> None:
    """Create all tables from schema.sql if they don't exist."""
    conn = get_connection()
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    logger.info("Database tables initialized")


def close_db() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.info("Database connection closed")


# ---------------------------------------------------------------------------
# Account helpers
# ---------------------------------------------------------------------------

def get_or_create_default_account(account_number: str = "default") -> int:
    """Return the ID of the default account, creating it if needed."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM accounts WHERE account_number = ?", (account_number,)
    ).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO accounts (name, account_number) VALUES (?, ?)",
        ("My Portfolio", account_number),
    )
    conn.commit()
    return cursor.lastrowid


def get_accounts() -> list[dict]:
    """Return all active accounts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM accounts WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Position helpers
# ---------------------------------------------------------------------------

def upsert_positions(account_id: int, positions: list[dict]) -> int:
    """Replace all positions for an account with fresh data.

    Deletes existing positions then inserts new ones so the table always
    reflects the latest broker state.  Returns the number of rows inserted.
    """
    conn = get_connection()
    conn.execute("DELETE FROM positions WHERE account_id = ?", (account_id,))
    now = datetime.utcnow().isoformat()
    for pos in positions:
        conn.execute(
            """INSERT INTO positions
               (account_id, ticker, name, quantity, avg_cost_basis,
                current_price, market_value, unrealized_pnl,
                unrealized_pnl_pct, asset_type, sector,
                last_updated, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                pos.get("ticker", ""),
                pos.get("name"),
                pos.get("quantity", 0),
                pos.get("avg_cost"),
                pos.get("current_price"),
                pos.get("market_value"),
                pos.get("unrealized_pnl"),
                pos.get("unrealized_pnl_pct"),
                pos.get("asset_type", "stock"),
                pos.get("sector"),
                now, now, now,
            ),
        )
    conn.commit()
    return len(positions)


def get_positions(account_id: Optional[int] = None) -> list[dict]:
    """Return positions, optionally filtered by account."""
    conn = get_connection()
    if account_id:
        rows = conn.execute(
            "SELECT * FROM positions WHERE account_id = ? ORDER BY market_value DESC",
            (account_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM positions ORDER BY market_value DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Trade helpers
# ---------------------------------------------------------------------------

def insert_trades(account_id: int, trades: list[dict]) -> int:
    """Insert a batch of trades. Returns number inserted."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    count = 0
    for t in trades:
        conn.execute(
            """INSERT INTO trades
               (account_id, ticker, side, quantity, price, fees,
                trade_date, notes, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                t.get("ticker", ""),
                t.get("side", "buy"),
                t.get("quantity", 0),
                t.get("price", 0),
                t.get("fees", 0),
                t.get("trade_date"),
                t.get("notes"),
                t.get("source", "ibkr_sync"),
                now, now,
            ),
        )
        count += 1
    conn.commit()
    return count


def insert_manual_trade(account_id: int, ticker: str, side: str,
                        quantity: float, price: float, trade_date: str,
                        fees: float = 0, notes: str = "") -> int:
    """Insert a single manually-entered trade. Returns the new row ID."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """INSERT INTO trades
           (account_id, ticker, side, quantity, price, fees,
            trade_date, notes, source, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)""",
        (account_id, ticker, side, quantity, price, fees,
         trade_date, notes, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def get_trades(account_id: Optional[int] = None, limit: int = 200) -> list[dict]:
    """Return recent trades, optionally filtered by account."""
    conn = get_connection()
    if account_id:
        rows = conn.execute(
            "SELECT * FROM trades WHERE account_id = ? ORDER BY trade_date DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY trade_date DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def save_snapshot(account_id: int, total_value: float,
                  cash_balance: float, invested_value: float) -> None:
    """Save or update today's portfolio snapshot."""
    conn = get_connection()
    today = date.today().isoformat()
    conn.execute(
        """INSERT INTO portfolio_snapshots
           (account_id, date, total_value, cash_balance, invested_value)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(account_id, date)
           DO UPDATE SET total_value=excluded.total_value,
                         cash_balance=excluded.cash_balance,
                         invested_value=excluded.invested_value""",
        (account_id, today, total_value, cash_balance, invested_value),
    )
    conn.commit()


def get_snapshots(account_id: Optional[int] = None,
                  days: Optional[int] = None) -> list[dict]:
    """Return portfolio snapshots, optionally filtered by account and recency."""
    conn = get_connection()
    query = "SELECT * FROM portfolio_snapshots"
    params: list = []
    clauses: list[str] = []

    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    if days:
        clauses.append("date >= date('now', ?)")
        params.append(f"-{days} days")

    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY date ASC"

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------

def add_to_watchlist(ticker: str, notes: str = "") -> None:
    """Add a ticker to the watchlist (ignores duplicates)."""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (ticker, notes) VALUES (?, ?)",
        (ticker.upper(), notes),
    )
    conn.commit()


def get_watchlist() -> list[dict]:
    """Return all watchlist items."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM watchlist ORDER BY added_date DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def remove_from_watchlist(ticker: str) -> None:
    """Remove a ticker from the watchlist."""
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


# ---------------------------------------------------------------------------
# Price cache helpers
# ---------------------------------------------------------------------------

def get_cached_prices(ticker: str, start_date: str,
                      end_date: str) -> list[dict]:
    """Return cached price rows for a ticker within a date range."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM price_cache
           WHERE ticker = ? AND date BETWEEN ? AND ?
           ORDER BY date ASC""",
        (ticker.upper(), start_date, end_date),
    ).fetchall()
    return [dict(r) for r in rows]


def save_price_cache(ticker: str, rows: list[dict]) -> int:
    """Bulk-insert price data into the cache. Skips duplicates. Returns count."""
    conn = get_connection()
    count = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO price_cache
                   (ticker, date, open, high, low, close, adjusted_close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker.upper(),
                    row.get("date"),
                    row.get("open"),
                    row.get("high"),
                    row.get("low"),
                    row.get("close"),
                    row.get("adjusted_close"),
                    row.get("volume"),
                ),
            )
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count
