-- InvestView Phase 1 Database Schema

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    broker TEXT NOT NULL CHECK (broker IN ('ibkr', 'etrade', 'csv_import')),
    account_number TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    avg_cost_basis REAL,
    current_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,
    asset_type TEXT NOT NULL DEFAULT 'stock'
        CHECK (asset_type IN ('stock', 'etf', 'option', 'bond', 'cash')),
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fees REAL NOT NULL DEFAULT 0,
    trade_date TIMESTAMP NOT NULL,
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('api_sync', 'csv_import', 'manual')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    date DATE NOT NULL,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL DEFAULT 0,
    invested_value REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON portfolio_snapshots(date);

CREATE TABLE IF NOT EXISTS price_cache (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    adjusted_close REAL,
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_price_cache_ticker ON price_cache(ticker);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
