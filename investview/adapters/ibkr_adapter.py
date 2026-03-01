"""Interactive Brokers adapter using ib_insync.

Connects to TWS or IB Gateway to download portfolio data, positions,
and trade history.  All calls are synchronous.
"""

import logging
from typing import Optional

from config import IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID

logger = logging.getLogger(__name__)

# Module-level IB instance so it persists across Dash callbacks
_ib = None


def _get_ib():
    """Lazy-import and return the module-level IB instance."""
    global _ib
    if _ib is None:
        from ib_insync import IB
        _ib = IB()
    return _ib


# ---------------------------------------------------------------------------
# Asset-type mapping: IBKR secType → our asset_type label
# ---------------------------------------------------------------------------
_ASSET_TYPE_MAP = {
    "STK": "stock",
    "ETF": "etf",
    "OPT": "option",
    "FUT": "future",
    "BOND": "bond",
    "CASH": "cash",
    "FOP": "option",
    "WAR": "warrant",
    "FUND": "fund",
}


class IBKRAdapter:
    """Wrapper around ib_insync for portfolio operations."""

    # ----- Connection -----

    def connect(self) -> bool:
        """Connect to TWS / IB Gateway.

        Returns True on success, False on failure.
        """
        ib = _get_ib()
        if ib.isConnected():
            logger.info("Already connected to IBKR")
            return True
        try:
            ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            ib.sleep(1)  # let account data populate
            logger.info("Connected to IBKR at %s:%s", IBKR_HOST, IBKR_PORT)
            return True
        except ConnectionRefusedError:
            logger.warning(
                "IBKR connection refused at %s:%s — is TWS/Gateway running?",
                IBKR_HOST, IBKR_PORT,
            )
            return False
        except Exception as exc:
            logger.error("IBKR connection error: %s", exc)
            return False

    def disconnect(self) -> None:
        """Cleanly disconnect from TWS / IB Gateway."""
        ib = _get_ib()
        if ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check whether we are currently connected."""
        ib = _get_ib()
        return ib.isConnected()

    # ----- Portfolio -----

    def get_account_summary(self) -> dict:
        """Return key account metrics as a flat dict.

        Keys: net_liquidation, total_cash, buying_power,
              realized_pnl, unrealized_pnl
        """
        ib = _get_ib()
        result = {
            "net_liquidation": 0.0,
            "total_cash": 0.0,
            "buying_power": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }
        try:
            summary = ib.accountSummary()
            tag_map = {
                "NetLiquidation": "net_liquidation",
                "TotalCashValue": "total_cash",
                "BuyingPower": "buying_power",
                "RealizedPnL": "realized_pnl",
                "UnrealizedPnL": "unrealized_pnl",
            }
            for item in summary:
                key = tag_map.get(item.tag)
                if key and item.currency == "USD":
                    try:
                        result[key] = float(item.value)
                    except (ValueError, TypeError):
                        pass
        except Exception as exc:
            logger.error("Failed to get account summary: %s", exc)
        return result

    def get_positions(self) -> list[dict]:
        """Return all current positions as a list of dicts."""
        ib = _get_ib()
        positions: list[dict] = []
        try:
            for item in ib.portfolio():
                contract = item.contract
                sec_type = getattr(contract, "secType", "STK")
                asset_type = _ASSET_TYPE_MAP.get(sec_type, "other")

                avg_cost = item.averageCost
                # For stocks, IBKR's averageCost is per share already
                # but for options it is per contract (×100)
                if sec_type == "OPT" and avg_cost:
                    avg_cost = avg_cost / 100.0

                market_value = item.marketValue
                unrealized_pnl = item.unrealizedPNL
                current_price = item.marketPrice
                quantity = item.position

                unrealized_pnl_pct = None
                cost_basis = avg_cost * quantity if avg_cost and quantity else None
                if cost_basis and cost_basis != 0:
                    unrealized_pnl_pct = (
                        (unrealized_pnl / abs(cost_basis)) * 100
                        if unrealized_pnl is not None else None
                    )

                positions.append({
                    "ticker": contract.symbol,
                    "name": getattr(contract, "localSymbol", contract.symbol),
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "current_price": current_price,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_pct": unrealized_pnl_pct,
                    "asset_type": asset_type,
                })
        except Exception as exc:
            logger.error("Failed to get positions: %s", exc)
        return positions

    def get_trade_history(self, days_back: int = 30) -> list[dict]:
        """Return recent trade executions as a list of dicts."""
        ib = _get_ib()
        trades: list[dict] = []
        try:
            fills = ib.fills()
            for fill in fills:
                execution = fill.execution
                contract = fill.contract
                trades.append({
                    "ticker": contract.symbol,
                    "side": "buy" if execution.side == "BOT" else "sell",
                    "quantity": abs(execution.shares),
                    "price": execution.price,
                    "fees": fill.commissionReport.commission
                            if fill.commissionReport else 0,
                    "trade_date": execution.time.isoformat()
                                  if execution.time else None,
                })
        except Exception as exc:
            logger.error("Failed to get trade history: %s", exc)
        return trades

    def get_account_value_history(self) -> list[dict]:
        """Pull daily account value history if available.

        Note: IBKR's API doesn't directly expose a daily NAV history
        endpoint, so this returns an empty list.  Portfolio snapshots
        are built up over time via the sync process instead.
        """
        logger.info("Account value history not available via IBKR API; "
                     "use portfolio snapshots instead.")
        return []
