"""Formatting helpers for currency, percentages, and colors."""

from typing import Optional


def fmt_currency(value: Optional[float], decimals: int = 2) -> str:
    """Format a number as USD currency, e.g. '$1,234.56'."""
    if value is None:
        return "—"
    prefix = "-" if value < 0 else ""
    return f"{prefix}${abs(value):,.{decimals}f}"


def fmt_pct(value: Optional[float], decimals: int = 2) -> str:
    """Format a number as a percentage, e.g. '+12.34%'."""
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def fmt_number(value: Optional[float], decimals: int = 2) -> str:
    """Format a number with commas, e.g. '1,234.56'."""
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def fmt_large_number(value: Optional[float]) -> str:
    """Format a large number with suffix, e.g. '1.23B'."""
    if value is None:
        return "—"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000_000:.2f}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.2f}M"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.2f}K"
    return f"{sign}{abs_val:,.2f}"


def pnl_color(value: Optional[float]) -> str:
    """Return a CSS color string based on positive/negative value."""
    if value is None or value == 0:
        return "gray"
    return "green" if value > 0 else "red"
