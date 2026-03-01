"""Reusable table formatting helpers for Dash DataTable."""

from dash import dash_table


def pnl_conditional_styles(column_id: str) -> list[dict]:
    """Return conditional style rules that color a column green/red by sign."""
    return [
        {
            "if": {
                "filter_query": f"{{{column_id}}} > 0",
                "column_id": column_id,
            },
            "color": "green",
            "fontWeight": "bold",
        },
        {
            "if": {
                "filter_query": f"{{{column_id}}} < 0",
                "column_id": column_id,
            },
            "color": "red",
            "fontWeight": "bold",
        },
    ]


# Default style settings for DataTables across the app
DEFAULT_TABLE_STYLE = {
    "style_table": {"overflowX": "auto"},
    "style_cell": {
        "textAlign": "right",
        "padding": "8px 12px",
        "fontSize": "0.9rem",
    },
    "style_header": {
        "fontWeight": "bold",
        "backgroundColor": "#f8f9fa",
        "borderBottom": "2px solid #dee2e6",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
    ],
}
