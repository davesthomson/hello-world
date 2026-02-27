"""CSV import adapter for manual data import."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from config import logger
from adapters.base import BrokerAdapter

# Preset column mappings for common brokerage CSV exports
PRESET_MAPPINGS: dict[str, dict[str, str]] = {
    "ibkr_activity": {
        "Symbol": "ticker",
        "Quantity": "quantity",
        "T. Price": "price",
        "Cost Basis": "avg_cost",
        "Date/Time": "trade_date",
        "Buy/Sell": "side",
        "Comm/Fee": "fees",
    },
    "etrade_export": {
        "Symbol": "ticker",
        "Quantity": "quantity",
        "Price": "price",
        "Amount": "avg_cost",
        "Transaction Date": "trade_date",
        "Transaction Type": "side",
        "Commission": "fees",
    },
    "generic": {
        "ticker": "ticker",
        "quantity": "quantity",
        "price": "price",
        "avg_cost": "avg_cost",
        "trade_date": "trade_date",
        "side": "side",
        "fees": "fees",
    },
}

REQUIRED_FIELDS = {"ticker", "quantity", "price"}


class CSVAdapter(BrokerAdapter):
    """Adapter for importing data from CSV files."""

    def __init__(self):
        self._data: list[dict] = []
        self._column_mapping: dict[str, str] = {}
        self._errors: list[str] = []

    def connect(self) -> bool:
        """No connection needed for CSV. Always returns True."""
        return True

    def load_csv(
        self,
        file_content: str | io.StringIO,
        column_mapping: dict[str, str] | None = None,
        preset: str | None = None,
    ) -> tuple[list[dict], list[str]]:
        """Parse CSV content and return (parsed_rows, errors).

        Args:
            file_content: CSV string or StringIO object.
            column_mapping: Dict mapping CSV column names → our field names.
            preset: Name of a preset mapping to use instead of column_mapping.

        Returns:
            Tuple of (list of parsed row dicts, list of error messages).
        """
        self._errors = []

        if preset and preset in PRESET_MAPPINGS:
            self._column_mapping = PRESET_MAPPINGS[preset]
        elif column_mapping:
            self._column_mapping = column_mapping
        else:
            self._column_mapping = PRESET_MAPPINGS["generic"]

        if isinstance(file_content, str):
            file_content = io.StringIO(file_content)

        reader = csv.DictReader(file_content)
        rows: list[dict] = []

        for i, raw_row in enumerate(reader, start=2):  # start=2 because row 1 is header
            mapped = self._map_row(raw_row, i)
            if mapped is not None:
                rows.append(mapped)

        self._data = rows
        logger.info("Parsed %d rows from CSV (%d errors)", len(rows), len(self._errors))
        return rows, self._errors

    def _map_row(self, raw_row: dict, row_num: int) -> dict | None:
        """Map a single CSV row to our schema, returning None on failure."""
        mapped: dict = {}
        for csv_col, our_field in self._column_mapping.items():
            value = raw_row.get(csv_col, "").strip()
            if value:
                mapped[our_field] = value

        # Validate required fields
        missing = REQUIRED_FIELDS - set(mapped.keys())
        if missing:
            self._errors.append(f"Row {row_num}: missing required fields: {', '.join(sorted(missing))}")
            return None

        # Type conversion and validation
        try:
            mapped["quantity"] = float(mapped["quantity"].replace(",", ""))
        except (ValueError, AttributeError):
            self._errors.append(f"Row {row_num}: invalid quantity '{mapped.get('quantity')}'")
            return None

        try:
            price_str = mapped["price"].replace(",", "").replace("$", "")
            mapped["price"] = float(price_str)
        except (ValueError, AttributeError):
            self._errors.append(f"Row {row_num}: invalid price '{mapped.get('price')}'")
            return None

        # Optional fields
        if "fees" in mapped:
            try:
                mapped["fees"] = float(str(mapped["fees"]).replace(",", "").replace("$", ""))
            except (ValueError, AttributeError):
                mapped["fees"] = 0.0

        if "avg_cost" in mapped:
            try:
                mapped["avg_cost"] = float(str(mapped["avg_cost"]).replace(",", "").replace("$", ""))
            except (ValueError, AttributeError):
                mapped["avg_cost"] = mapped["price"]

        # Normalize side
        side_raw = mapped.get("side", "buy").lower().strip()
        if side_raw in ("buy", "bot", "bought", "b", "long"):
            mapped["side"] = "buy"
        elif side_raw in ("sell", "sld", "sold", "s", "short"):
            mapped["side"] = "sell"
        else:
            mapped["side"] = "buy"

        # Parse date
        if "trade_date" in mapped:
            mapped["trade_date"] = self._parse_date(mapped["trade_date"], row_num)
        else:
            mapped["trade_date"] = datetime.now().isoformat()

        mapped["ticker"] = mapped["ticker"].upper().strip()
        mapped["source"] = "csv_import"
        return mapped

    def _parse_date(self, date_str: str, row_num: int) -> str:
        """Try several date formats and return ISO format string."""
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%Y%m%d",
            "%d-%b-%Y",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).isoformat()
            except ValueError:
                continue
        self._errors.append(f"Row {row_num}: could not parse date '{date_str}', using current time")
        return datetime.now().isoformat()

    def get_positions(self) -> list[dict]:
        """Return loaded data mapped as positions.

        For CSV imports, each row is treated as either a trade or a position
        depending on available fields.
        """
        positions: list[dict] = []
        for row in self._data:
            positions.append({
                "ticker": row["ticker"],
                "quantity": row["quantity"],
                "avg_cost_basis": row.get("avg_cost", row["price"]),
                "current_price": row["price"],
                "market_value": row["quantity"] * row["price"],
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
                "asset_type": "stock",
            })
        return positions

    def get_trades(self) -> list[dict]:
        """Return loaded data mapped as trades."""
        return [
            {
                "ticker": row["ticker"],
                "side": row.get("side", "buy"),
                "quantity": row["quantity"],
                "price": row["price"],
                "fees": row.get("fees", 0),
                "trade_date": row.get("trade_date", datetime.now().isoformat()),
                "notes": "CSV import",
                "source": "csv_import",
            }
            for row in self._data
        ]

    def get_account_summary(self) -> dict:
        """CSV adapter doesn't provide account summaries."""
        return {}

    def get_trade_history(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        """Return loaded trades (date filtering not applicable for CSV)."""
        return self.get_trades()

    def disconnect(self) -> None:
        """No connection to close."""
        self._data = []
