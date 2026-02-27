"""Formatting helpers for currency, percentages, and color coding."""

from __future__ import annotations


def fmt_currency(value: float | None, symbol: str = "$") -> str:
    """Format a number as currency. Returns '—' for None."""
    if value is None:
        return "—"
    if abs(value) >= 1_000_000:
        return f"{symbol}{value:,.0f}"
    return f"{symbol}{value:,.2f}"


def fmt_pct(value: float | None, decimals: int = 2) -> str:
    """Format a number as a percentage. Returns '—' for None."""
    if value is None:
        return "—"
    return f"{value:+.{decimals}f}%"


def fmt_number(value: float | None, decimals: int = 2) -> str:
    """Format a plain number with commas. Returns '—' for None."""
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def fmt_large_number(value: float | None) -> str:
    """Format large numbers with K/M/B suffixes."""
    if value is None:
        return "—"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.2f}M"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.1f}K"
    return f"{sign}{abs_val:,.2f}"


def pnl_color(value: float | None) -> str:
    """Return a CSS color string based on positive/negative value."""
    if value is None or value == 0:
        return "gray"
    return "green" if value > 0 else "red"


def pnl_arrow(value: float | None) -> str:
    """Return an up/down arrow character based on positive/negative value."""
    if value is None or value == 0:
        return "→"
    return "▲" if value > 0 else "▼"
