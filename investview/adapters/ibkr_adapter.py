"""Interactive Brokers adapter using ib_insync."""

from __future__ import annotations

import socket
from datetime import datetime

from config import IBKR_CLIENT_ID, IBKR_HOST, IBKR_PORT, logger
from adapters.base import BrokerAdapter

# Asset type mapping from IBKR security types to our schema
_IBKR_ASSET_MAP = {
    "STK": "stock",
    "ETF": "etf",
    "OPT": "option",
    "BOND": "bond",
    "CASH": "cash",
    "FUT": "stock",   # map futures to stock for Phase 1
    "FUND": "etf",    # mutual funds → etf bucket
}


def is_gateway_running(host: str = IBKR_HOST, port: int = IBKR_PORT, timeout: float = 2.0) -> bool:
    """Check whether TWS or IB Gateway is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


class IBKRAdapter(BrokerAdapter):
    """Adapter for Interactive Brokers via ib_insync."""

    def __init__(self, host: str = IBKR_HOST, port: int = IBKR_PORT, client_id: int = IBKR_CLIENT_ID):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = None

    def connect(self) -> bool:
        """Connect to TWS / IB Gateway. Returns True on success."""
        try:
            from ib_insync import IB
            self.ib = IB()
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=10)
            logger.info("Connected to IBKR at %s:%s", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to connect to IBKR: %s", e)
            self.ib = None
            return False

    def _ensure_connected(self) -> None:
        if self.ib is None or not self.ib.isConnected():
            raise ConnectionError("Not connected to IBKR. Call connect() first.")

    def get_positions(self) -> list[dict]:
        """Fetch current positions from IBKR."""
        self._ensure_connected()
        positions = []
        for pos in self.ib.positions():
            contract = pos.contract
            sec_type = _IBKR_ASSET_MAP.get(contract.secType, "stock")
            avg_cost = pos.avgCost
            qty = pos.position

            # Request market data for current price
            current_price = None
            market_value = None
            unrealized_pnl = None
            unrealized_pnl_pct = None
            try:
                self.ib.qualifyContracts(contract)
                ticker = self.ib.reqMktData(contract, snapshot=True)
                self.ib.sleep(2)  # allow time for snapshot
                if ticker.last and ticker.last > 0:
                    current_price = ticker.last
                elif ticker.close and ticker.close > 0:
                    current_price = ticker.close

                if current_price and qty:
                    market_value = current_price * qty
                    cost_basis_total = avg_cost * qty
                    unrealized_pnl = market_value - cost_basis_total
                    if cost_basis_total != 0:
                        unrealized_pnl_pct = (unrealized_pnl / abs(cost_basis_total)) * 100
                self.ib.cancelMktData(contract)
            except Exception as e:
                logger.warning("Could not get market data for %s: %s", contract.symbol, e)

            positions.append({
                "ticker": contract.symbol,
                "quantity": float(qty),
                "avg_cost_basis": float(avg_cost) if avg_cost else None,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": unrealized_pnl_pct,
                "asset_type": sec_type,
            })
        logger.info("Fetched %d positions from IBKR", len(positions))
        return positions

    def get_account_summary(self) -> dict:
        """Fetch account summary from IBKR."""
        self._ensure_connected()
        summary = {}
        try:
            acct_values = self.ib.accountSummary()
            val_map = {}
            for av in acct_values:
                val_map[av.tag] = av.value

            summary = {
                "total_value": float(val_map.get("NetLiquidation", 0)),
                "cash_balance": float(val_map.get("TotalCashValue", 0)),
                "buying_power": float(val_map.get("BuyingPower", 0)),
                "invested_value": float(val_map.get("GrossPositionValue", 0)),
            }
        except Exception as e:
            logger.error("Failed to get IBKR account summary: %s", e)
        return summary

    def get_trade_history(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        """Fetch trade executions from IBKR.

        Note: ib_insync only returns executions from the current session or recent
        trading day. For full history, use Flex Queries or activity statements.
        """
        self._ensure_connected()
        trades = []
        try:
            from ib_insync import ExecutionFilter
            exec_filter = ExecutionFilter()
            fills = self.ib.reqExecutions(exec_filter)

            for fill in fills:
                execution = fill.execution
                contract = fill.contract
                trade_dt = datetime.strptime(execution.time, "%Y%m%d  %H:%M:%S") if isinstance(execution.time, str) else execution.time
                side = "buy" if execution.side == "BOT" else "sell"

                trades.append({
                    "ticker": contract.symbol,
                    "side": side,
                    "quantity": float(execution.shares),
                    "price": float(execution.price),
                    "fees": float(fill.commissionReport.commission) if fill.commissionReport else 0,
                    "trade_date": trade_dt.isoformat(),
                    "notes": f"IBKR Order #{execution.orderId}",
                    "source": "api_sync",
                })
        except Exception as e:
            logger.error("Failed to get IBKR trade history: %s", e)
        logger.info("Fetched %d trades from IBKR", len(trades))
        return trades

    def disconnect(self) -> None:
        """Disconnect from IBKR."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")
        self.ib = None
