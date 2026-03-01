"""Reusable metric card components."""

import dash_bootstrap_components as dbc
from dash import html

from utils.formatting import pnl_color


def metric_card(title: str, value: str, subtitle: str = "",
                color: str | None = None) -> dbc.Card:
    """A single metric card showing a title, large value, and subtitle.

    Args:
        title: Card header text (e.g. "Total Value").
        value: Main display value (already formatted).
        subtitle: Smaller text below the value (optional).
        color: CSS color for the value text. If None, uses default.
    """
    value_style = {}
    if color:
        value_style["color"] = color

    return dbc.Card(
        dbc.CardBody([
            html.P(title, className="text-muted mb-1",
                   style={"fontSize": "0.85rem"}),
            html.H4(value, className="mb-0 fw-bold", style=value_style),
            html.Small(subtitle, className="text-muted") if subtitle else None,
        ]),
        className="shadow-sm",
    )
