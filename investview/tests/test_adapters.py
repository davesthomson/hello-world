"""Tests for CSV adapter and adapter validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from adapters.csv_adapter import CSVAdapter, PRESET_MAPPINGS


class TestCSVAdapter:
    def test_parse_generic_csv(self):
        csv_content = """ticker,quantity,price,side,trade_date,fees
AAPL,100,150.50,buy,2024-01-15,1.00
MSFT,50,300.25,sell,2024-02-20,0.50
GOOG,25,140.00,buy,2024-03-10,0.75
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(errors) == 0
        assert len(rows) == 3
        assert rows[0]["ticker"] == "AAPL"
        assert rows[0]["quantity"] == 100.0
        assert rows[0]["price"] == 150.50
        assert rows[0]["side"] == "buy"
        assert rows[1]["side"] == "sell"

    def test_missing_required_fields(self):
        csv_content = """ticker,quantity
AAPL,100
MSFT,50
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 0
        assert len(errors) == 2
        assert "missing required fields" in errors[0].lower()

    def test_invalid_quantity(self):
        csv_content = """ticker,quantity,price
AAPL,abc,150.00
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 0
        assert len(errors) == 1
        assert "invalid quantity" in errors[0].lower()

    def test_invalid_price(self):
        csv_content = """ticker,quantity,price
AAPL,100,not_a_price
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 0
        assert len(errors) == 1
        assert "invalid price" in errors[0].lower()

    def test_side_normalization(self):
        csv_content = """ticker,quantity,price,side
AAPL,100,150,BOT
MSFT,50,300,SLD
GOOG,25,140,Bought
TSLA,10,200,Sold
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 4
        assert rows[0]["side"] == "buy"
        assert rows[1]["side"] == "sell"
        assert rows[2]["side"] == "buy"
        assert rows[3]["side"] == "sell"

    def test_date_parsing_formats(self):
        csv_content = """ticker,quantity,price,trade_date
AAPL,100,150,2024-01-15
MSFT,50,300,01/20/2024
GOOG,25,140,20240305
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 3
        assert "2024-01-15" in rows[0]["trade_date"]
        assert "2024-01-20" in rows[1]["trade_date"]
        assert "2024-03-05" in rows[2]["trade_date"]

    def test_currency_symbols_stripped(self):
        csv_content = """ticker,quantity,price,fees
AAPL,100,$150.50,$1.00
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 1
        assert rows[0]["price"] == 150.50
        assert rows[0]["fees"] == 1.00

    def test_comma_separated_numbers(self):
        csv_content = """ticker,quantity,price
AAPL,"1,000","1,250.50"
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 1
        assert rows[0]["quantity"] == 1000.0
        assert rows[0]["price"] == 1250.50

    def test_get_positions(self):
        csv_content = """ticker,quantity,price
AAPL,100,150
MSFT,50,300
"""
        adapter = CSVAdapter()
        adapter.load_csv(csv_content, preset="generic")
        positions = adapter.get_positions()

        assert len(positions) == 2
        assert positions[0]["ticker"] == "AAPL"
        assert positions[0]["market_value"] == 15000.0

    def test_get_trades(self):
        csv_content = """ticker,quantity,price,side,trade_date
AAPL,100,150,buy,2024-01-15
"""
        adapter = CSVAdapter()
        adapter.load_csv(csv_content, preset="generic")
        trades = adapter.get_trades()

        assert len(trades) == 1
        assert trades[0]["side"] == "buy"
        assert trades[0]["source"] == "csv_import"

    def test_connect_always_true(self):
        adapter = CSVAdapter()
        assert adapter.connect() is True

    def test_preset_mappings_exist(self):
        assert "generic" in PRESET_MAPPINGS
        assert "ibkr_activity" in PRESET_MAPPINGS
        assert "etrade_export" in PRESET_MAPPINGS

    def test_custom_column_mapping(self):
        csv_content = """Symbol,Qty,Amount
AAPL,100,150.50
"""
        mapping = {"Symbol": "ticker", "Qty": "quantity", "Amount": "price"}
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, column_mapping=mapping)

        assert len(rows) == 1
        assert rows[0]["ticker"] == "AAPL"
        assert rows[0]["quantity"] == 100.0

    def test_empty_csv(self):
        csv_content = """ticker,quantity,price
"""
        adapter = CSVAdapter()
        rows, errors = adapter.load_csv(csv_content, preset="generic")

        assert len(rows) == 0
        assert len(errors) == 0
