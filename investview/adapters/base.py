"""Abstract base class for brokerage adapters."""

from abc import ABC, abstractmethod


class BrokerAdapter(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection. Return True if successful."""
        pass

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Return current positions as list of dicts matching positions table schema."""
        pass

    @abstractmethod
    def get_account_summary(self) -> dict:
        """Return account summary: total_value, cash, buying_power, etc."""
        pass

    @abstractmethod
    def get_trade_history(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        """Return historical trades matching trades table schema."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        pass
