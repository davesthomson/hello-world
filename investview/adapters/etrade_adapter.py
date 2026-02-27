"""E*Trade adapter using pyetrade."""

from __future__ import annotations

from config import (
    ETRADE_BASE_URL,
    ETRADE_CONSUMER_KEY,
    ETRADE_CONSUMER_SECRET,
    ETRADE_SANDBOX,
    logger,
)
from adapters.base import BrokerAdapter

# E*Trade URLs
# Sandbox: https://apisb.etrade.com
# Production: https://api.etrade.com


class ETradeAdapter(BrokerAdapter):
    """Adapter for E*Trade via pyetrade OAuth flow."""

    def __init__(self):
        self.consumer_key = ETRADE_CONSUMER_KEY
        self.consumer_secret = ETRADE_CONSUMER_SECRET
        self.sandbox = ETRADE_SANDBOX
        self.base_url = ETRADE_BASE_URL
        self.session = None
        self.accounts_client = None
        self.orders_client = None
        self.account_id_key = None

    def connect(self) -> bool:
        """Initiate OAuth flow with E*Trade.

        In a Streamlit context this requires user interaction — the OAuth
        verifier code must be entered by the user. This method handles the
        initial authorization URL generation and token exchange.
        """
        if not self.consumer_key or not self.consumer_secret:
            logger.error("E*Trade consumer key/secret not configured")
            return False

        try:
            import pyetrade

            oauth = pyetrade.ETradeOAuth(self.consumer_key, self.consumer_secret)
            authorize_url = oauth.get_request_token()
            logger.info("E*Trade authorize URL: %s", authorize_url)

            # In Streamlit, the verifier would be collected via st.text_input.
            # Store the oauth object so the verifier can be submitted later.
            self._oauth = oauth
            self._authorize_url = authorize_url
            return True
        except Exception as e:
            logger.error("E*Trade OAuth init failed: %s", e)
            return False

    def complete_oauth(self, verifier: str) -> bool:
        """Complete OAuth by exchanging the verifier for access tokens."""
        try:
            import pyetrade

            tokens = self._oauth.get_access_token(verifier)
            self.session = pyetrade.ETradeAccounts(
                self.consumer_key,
                self.consumer_secret,
                tokens["oauth_token"],
                tokens["oauth_token_secret"],
                dev=self.sandbox,
            )
            self.orders_client = pyetrade.ETradeOrder(
                self.consumer_key,
                self.consumer_secret,
                tokens["oauth_token"],
                tokens["oauth_token_secret"],
                dev=self.sandbox,
            )
            # Get the first account key
            accounts_list = self.session.list_accounts(resp_format="json")
            account_data = accounts_list["AccountListResponse"]["Accounts"]["Account"]
            if account_data:
                self.account_id_key = account_data[0]["accountIdKey"]
            logger.info("E*Trade OAuth complete, connected.")
            return True
        except Exception as e:
            logger.error("E*Trade OAuth completion failed: %s", e)
            return False

    def get_positions(self) -> list[dict]:
        """Fetch current positions from E*Trade."""
        if not self.session or not self.account_id_key:
            logger.error("E*Trade not connected. Call connect() and complete_oauth() first.")
            return []

        positions = []
        try:
            response = self.session.get_account_portfolio(
                self.account_id_key, resp_format="json"
            )
            portfolio_data = response.get("PortfolioResponse", {}).get("AccountPortfolio", [])
            for acct_portfolio in portfolio_data:
                for pos in acct_portfolio.get("Position", []):
                    product = pos.get("Product", {})
                    sec_type = product.get("securityType", "EQ")
                    asset_type = _map_etrade_type(sec_type)

                    qty = float(pos.get("quantity", 0))
                    cost_basis = float(pos.get("costPerShare", 0))
                    current_price = float(pos.get("Quick", {}).get("lastTrade", 0))
                    market_value = float(pos.get("marketValue", 0))
                    pnl = float(pos.get("totalGain", 0))
                    pnl_pct = float(pos.get("totalGainPct", 0))

                    positions.append({
                        "ticker": product.get("symbol", ""),
                        "quantity": qty,
                        "avg_cost_basis": cost_basis,
                        "current_price": current_price,
                        "market_value": market_value,
                        "unrealized_pnl": pnl,
                        "unrealized_pnl_pct": pnl_pct,
                        "asset_type": asset_type,
                    })
        except Exception as e:
            logger.error("Failed to fetch E*Trade positions: %s", e)
        logger.info("Fetched %d positions from E*Trade", len(positions))
        return positions

    def get_account_summary(self) -> dict:
        """Fetch account balance/summary from E*Trade."""
        if not self.session or not self.account_id_key:
            return {}
        try:
            response = self.session.get_account_balance(
                self.account_id_key, resp_format="json", real_time_nav=True
            )
            balance = response.get("BalanceResponse", {})
            computed = balance.get("Computed", {}).get("RealTimeValues", {})
            return {
                "total_value": float(computed.get("totalAccountValue", 0)),
                "cash_balance": float(balance.get("Computed", {}).get("cashAvailableForInvestment", 0)),
                "buying_power": float(balance.get("Computed", {}).get("cashBuyingPower", 0)),
                "invested_value": float(computed.get("totalAccountValue", 0))
                - float(balance.get("Computed", {}).get("cashAvailableForInvestment", 0)),
            }
        except Exception as e:
            logger.error("Failed to get E*Trade account summary: %s", e)
            return {}

    def get_trade_history(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        """Fetch order/trade history from E*Trade.

        Note: E*Trade's transaction API returns orders, not individual fills.
        This maps completed orders to our trades schema.
        """
        if not self.session or not self.account_id_key:
            return []
        trades = []
        try:
            params = {}
            if start_date:
                params["fromDate"] = start_date.replace("-", "")[:8]  # MMDDYYYY
            if end_date:
                params["toDate"] = end_date.replace("-", "")[:8]

            response = self.session.list_transactions(
                self.account_id_key, resp_format="json", **params
            )
            txn_list = response.get("TransactionListResponse", {}).get("Transaction", [])
            for txn in txn_list:
                if txn.get("transactionType") in ("Buy", "Sell"):
                    brokerage = txn.get("brokerage", {})
                    trades.append({
                        "ticker": brokerage.get("product", {}).get("symbol", ""),
                        "side": "buy" if txn["transactionType"] == "Buy" else "sell",
                        "quantity": float(brokerage.get("quantity", 0)),
                        "price": float(brokerage.get("price", 0)),
                        "fees": float(brokerage.get("commission", 0)) + float(brokerage.get("fee", 0)),
                        "trade_date": txn.get("transactionDate", ""),
                        "notes": txn.get("description", ""),
                        "source": "api_sync",
                    })
        except Exception as e:
            logger.error("Failed to get E*Trade trade history: %s", e)
        logger.info("Fetched %d trades from E*Trade", len(trades))
        return trades

    def disconnect(self) -> None:
        """No persistent connection to close for E*Trade REST API."""
        self.session = None
        self.orders_client = None
        self.account_id_key = None
        logger.info("E*Trade session cleared")


def _map_etrade_type(sec_type: str) -> str:
    """Map E*Trade security type codes to our asset_type enum."""
    mapping = {
        "EQ": "stock",
        "ETF": "etf",
        "OPTN": "option",
        "BOND": "bond",
        "MF": "etf",
        "MMF": "cash",
    }
    return mapping.get(sec_type, "stock")
