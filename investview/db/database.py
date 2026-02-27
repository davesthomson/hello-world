"""SQLite database connection helper and migration runner."""

import re
import sqlite3
from pathlib import Path

from config import DB_PATH, logger

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Return a SQLite connection with WAL mode and foreign keys enabled."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Run the schema SQL to create tables if they don't exist."""
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.commit()
    logger.info("Database initialized successfully.")


def reset_db(conn: sqlite3.Connection) -> None:
    """Drop all tables and re-create them. Use with caution."""
    tables = [
        "watchlist",
        "price_cache",
        "portfolio_snapshots",
        "trades",
        "positions",
        "accounts",
    ]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    init_db(conn)
    logger.info("Database reset complete.")


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def insert_account(
    conn: sqlite3.Connection,
    name: str,
    broker: str,
    account_number: str = "",
    is_active: bool = True,
) -> int:
    """Insert a new account and return its id."""
    cur = conn.execute(
        "INSERT INTO accounts (name, broker, account_number, is_active) VALUES (?, ?, ?, ?)",
        (name, broker, account_number, int(is_active)),
    )
    conn.commit()
    return cur.lastrowid


def get_accounts(conn: sqlite3.Connection, active_only: bool = True) -> list[sqlite3.Row]:
    """Return all accounts, optionally filtered to active only."""
    if active_only:
        return conn.execute("SELECT * FROM accounts WHERE is_active = 1").fetchall()
    return conn.execute("SELECT * FROM accounts").fetchall()


def upsert_positions(conn: sqlite3.Connection, account_id: int, positions: list[dict]) -> int:
    """Replace all positions for an account with a fresh snapshot.

    Deletes existing positions for the account, then inserts the new ones.
    Returns the number of rows inserted.
    """
    conn.execute("DELETE FROM positions WHERE account_id = ?", (account_id,))
    count = 0
    for pos in positions:
        conn.execute(
            """INSERT INTO positions
               (account_id, ticker, quantity, avg_cost_basis, current_price,
                market_value, unrealized_pnl, unrealized_pnl_pct, asset_type, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                account_id,
                pos["ticker"],
                pos.get("quantity", 0),
                pos.get("avg_cost_basis"),
                pos.get("current_price"),
                pos.get("market_value"),
                pos.get("unrealized_pnl"),
                pos.get("unrealized_pnl_pct"),
                pos.get("asset_type", "stock"),
            ),
        )
        count += 1
    conn.commit()
    return count


def get_positions(
    conn: sqlite3.Connection,
    account_id: int | None = None,
    asset_type: str | None = None,
) -> list[sqlite3.Row]:
    """Return positions with optional filters."""
    query = "SELECT p.*, a.name as account_name, a.broker FROM positions p JOIN accounts a ON p.account_id = a.id WHERE 1=1"
    params: list = []
    if account_id is not None:
        query += " AND p.account_id = ?"
        params.append(account_id)
    if asset_type:
        query += " AND p.asset_type = ?"
        params.append(asset_type)
    query += " ORDER BY p.market_value DESC"
    return conn.execute(query, params).fetchall()


def insert_trades(conn: sqlite3.Connection, trades: list[dict]) -> int:
    """Bulk-insert trades. Returns number of rows inserted."""
    count = 0
    for t in trades:
        conn.execute(
            """INSERT INTO trades
               (account_id, ticker, side, quantity, price, fees, trade_date, notes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t["account_id"],
                t["ticker"],
                t["side"],
                t["quantity"],
                t["price"],
                t.get("fees", 0),
                t["trade_date"],
                t.get("notes", ""),
                t.get("source", "manual"),
            ),
        )
        count += 1
    conn.commit()
    return count


def get_trades(
    conn: sqlite3.Connection,
    account_id: int | None = None,
    ticker: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    """Return trades with optional filters."""
    query = "SELECT t.*, a.name as account_name FROM trades t JOIN accounts a ON t.account_id = a.id WHERE 1=1"
    params: list = []
    if account_id is not None:
        query += " AND t.account_id = ?"
        params.append(account_id)
    if ticker:
        query += " AND t.ticker = ?"
        params.append(ticker)
    if start_date:
        query += " AND t.trade_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND t.trade_date <= ?"
        params.append(end_date)
    query += " ORDER BY t.trade_date DESC"
    return conn.execute(query, params).fetchall()


def upsert_snapshot(
    conn: sqlite3.Connection,
    account_id: int | None,
    date: str,
    total_value: float,
    cash_balance: float = 0,
    invested_value: float = 0,
) -> None:
    """Insert or replace a portfolio snapshot for a given account and date."""
    conn.execute(
        """INSERT INTO portfolio_snapshots (account_id, date, total_value, cash_balance, invested_value)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(account_id, date) DO UPDATE SET
               total_value = excluded.total_value,
               cash_balance = excluded.cash_balance,
               invested_value = excluded.invested_value,
               updated_at = CURRENT_TIMESTAMP""",
        (account_id, date, total_value, cash_balance, invested_value),
    )
    conn.commit()


def get_snapshots(
    conn: sqlite3.Connection,
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    """Return portfolio snapshots with optional filters."""
    query = "SELECT * FROM portfolio_snapshots WHERE 1=1"
    params: list = []
    if account_id is not None:
        query += " AND account_id = ?"
        params.append(account_id)
    else:
        query += " AND account_id IS NULL"
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date ASC"
    return conn.execute(query, params).fetchall()


def add_to_watchlist(conn: sqlite3.Connection, ticker: str, notes: str = "") -> None:
    """Add a ticker to the watchlist. Ignores duplicates."""
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (ticker, notes) VALUES (?, ?)",
        (ticker.upper(), notes),
    )
    conn.commit()


def remove_from_watchlist(conn: sqlite3.Connection, ticker: str) -> None:
    """Remove a ticker from the watchlist."""
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


def get_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all watchlist tickers."""
    return conn.execute("SELECT * FROM watchlist ORDER BY ticker").fetchall()


# Equity tickers are letters only (possibly with a space, dot, or hyphen for
# class shares like "BRK B", "BRK.B", "BRK-B").  CUSIPs and bond IDs always
# contain digits (e.g. "196711TP0").  Reject anything with digits or longer
# than 6 base characters.
_TICKER_RE = re.compile(r"^[A-Z]{1,6}([. -][A-Z]{1,2})?$")


def is_equity_ticker(ticker: str) -> bool:
    """Return True if *ticker* looks like a stock/ETF symbol (not a CUSIP or bond ID)."""
    return bool(_TICKER_RE.match(ticker))


def yfinance_ticker(ticker: str) -> str:
    """Convert an IBKR-style ticker to the yfinance format.

    IBKR uses spaces for class shares (``PBR A``, ``BRK B``) while yfinance
    expects hyphens (``PBR-A``, ``BRK-B``).
    """
    return ticker.replace(" ", "-")


def refresh_position_prices(conn: sqlite3.Connection, account_id: int | None = None) -> int:
    """Use yfinance to update current_price, market_value, and P&L for stored positions.

    Only targets positions whose tickers look like equity/ETF symbols
    (skips CUSIPs, bond identifiers, etc.).  Returns the number of positions updated.
    """
    from data.market_data import get_multiple_prices

    positions = get_positions(conn, account_id=account_id)
    if not positions:
        return 0

    # Collect unique equity tickers that yfinance can resolve
    db_tickers = sorted({p["ticker"] for p in positions if is_equity_ticker(p["ticker"])})
    if not db_tickers:
        return 0

    # Map DB ticker → yfinance ticker (spaces → hyphens for class shares)
    yf_map = {t: yfinance_ticker(t) for t in db_tickers}
    yf_tickers = list(yf_map.values())

    prices = get_multiple_prices(yf_tickers)

    # Build reverse lookup: DB ticker → price
    db_prices: dict[str, float | None] = {}
    for db_t, yf_t in yf_map.items():
        db_prices[db_t] = prices.get(yf_t)

    updated = 0
    for pos in positions:
        ticker = pos["ticker"]
        price = db_prices.get(ticker)
        if price is None:
            continue

        qty = pos["quantity"] or 0
        avg_cost = pos["avg_cost_basis"]
        market_value = price * qty
        unrealized_pnl = None
        unrealized_pnl_pct = None
        if avg_cost and qty:
            cost_basis_total = avg_cost * qty
            unrealized_pnl = market_value - cost_basis_total
            if cost_basis_total != 0:
                unrealized_pnl_pct = (unrealized_pnl / abs(cost_basis_total)) * 100

        conn.execute(
            """UPDATE positions
               SET current_price = ?, market_value = ?,
                   unrealized_pnl = ?, unrealized_pnl_pct = ?,
                   last_updated = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (price, market_value, unrealized_pnl, unrealized_pnl_pct, pos["id"]),
        )
        updated += 1

    conn.commit()
    logger.info("Refreshed prices for %d positions via yfinance.", updated)
    return updated
