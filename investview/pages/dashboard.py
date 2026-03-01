"""Dashboard page — high-level portfolio summary."""

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc, callback, Output, Input, dash_table

from components.cards import metric_card
from components.tables import pnl_conditional_styles, DEFAULT_TABLE_STYLE
from db.database import get_positions, get_snapshots, get_accounts
from utils.formatting import fmt_currency, fmt_pct, pnl_color

dash.register_page(__name__, path="/", name="Dashboard")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container([
    # Account filter
    dbc.Row(
        dbc.Col(
            dcc.Dropdown(
                id="dash-account-filter",
                placeholder="All Accounts",
                clearable=True,
            ),
            width=3,
        ),
        className="mb-3",
    ),

    # Metric cards row
    dbc.Row(id="dash-metric-cards", className="mb-4 g-3"),

    # Middle section: holdings table + allocation charts
    dbc.Row([
        # Holdings table
        dbc.Col([
            html.H5("Top Holdings"),
            dash_table.DataTable(
                id="dash-holdings-table",
                columns=[
                    {"name": "Ticker", "id": "ticker"},
                    {"name": "Name", "id": "name"},
                    {"name": "Shares", "id": "quantity", "type": "numeric",
                     "format": {"specifier": ",.0f"}},
                    {"name": "Price", "id": "current_price", "type": "numeric",
                     "format": {"specifier": "$,.2f"}},
                    {"name": "Mkt Value", "id": "market_value", "type": "numeric",
                     "format": {"specifier": "$,.0f"}},
                    {"name": "P&L", "id": "unrealized_pnl", "type": "numeric",
                     "format": {"specifier": "$,.2f"}},
                    {"name": "P&L %", "id": "unrealized_pnl_pct", "type": "numeric",
                     "format": {"specifier": "+.2f"}},
                ],
                sort_action="native",
                page_size=10,
                style_cell_conditional=[
                    {"if": {"column_id": "ticker"}, "textAlign": "left"},
                    {"if": {"column_id": "name"}, "textAlign": "left"},
                ],
                **(DEFAULT_TABLE_STYLE),
            ),
        ], md=7),

        # Allocation charts
        dbc.Col([
            html.H5("Asset Allocation"),
            dcc.Graph(id="dash-asset-donut", config={"displayModeBar": False}),
            html.H5("Sector Allocation", className="mt-3"),
            dcc.Graph(id="dash-sector-donut", config={"displayModeBar": False}),
        ], md=5),
    ], className="mb-4"),

    # Portfolio value chart
    dbc.Row([
        dbc.Col([
            html.H5("Portfolio Value Over Time"),
            dbc.ButtonGroup([
                dbc.Button("1M", id="dash-range-1m", size="sm", outline=True,
                           color="primary"),
                dbc.Button("3M", id="dash-range-3m", size="sm", outline=True,
                           color="primary"),
                dbc.Button("6M", id="dash-range-6m", size="sm", outline=True,
                           color="primary"),
                dbc.Button("YTD", id="dash-range-ytd", size="sm", outline=True,
                           color="primary"),
                dbc.Button("1Y", id="dash-range-1y", size="sm", outline=True,
                           color="primary", active=True),
                dbc.Button("ALL", id="dash-range-all", size="sm", outline=True,
                           color="primary"),
            ], className="mb-2"),
            dcc.Graph(id="dash-portfolio-chart"),
        ]),
    ]),

    # Auto-refresh every 60 seconds
    dcc.Interval(id="dash-interval", interval=60_000, n_intervals=0),
], fluid=True)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("dash-account-filter", "options"),
    Input("dash-interval", "n_intervals"),
)
def update_account_options(_n):
    """Populate the account dropdown."""
    accounts = get_accounts()
    return [{"label": a["name"], "value": a["id"]} for a in accounts]


@callback(
    Output("dash-metric-cards", "children"),
    Output("dash-holdings-table", "data"),
    Output("dash-asset-donut", "figure"),
    Output("dash-sector-donut", "figure"),
    Input("dash-interval", "n_intervals"),
    Input("dash-account-filter", "value"),
)
def update_dashboard(_n, account_id):
    """Refresh metric cards, holdings table, and allocation charts."""
    positions = get_positions(account_id)

    # Compute totals
    total_value = sum(p.get("market_value") or 0 for p in positions)
    total_pnl = sum(p.get("unrealized_pnl") or 0 for p in positions)
    total_cost = sum(
        (p.get("avg_cost_basis") or 0) * (p.get("quantity") or 0)
        for p in positions
    )
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

    # Metric cards
    cards = dbc.Row([
        dbc.Col(metric_card("Total Portfolio Value",
                            fmt_currency(total_value)), md=3),
        dbc.Col(metric_card("Unrealized P&L",
                            fmt_currency(total_pnl),
                            subtitle=fmt_pct(total_pnl_pct),
                            color=pnl_color(total_pnl)), md=3),
        dbc.Col(metric_card("Positions",
                            str(len(positions))), md=3),
        dbc.Col(metric_card("Avg P&L %",
                            fmt_pct(total_pnl_pct),
                            color=pnl_color(total_pnl_pct)), md=3),
    ], className="g-3")

    # Holdings table (top 10)
    table_data = sorted(
        positions, key=lambda p: p.get("market_value") or 0, reverse=True
    )[:10]

    # Asset allocation donut
    asset_groups: dict[str, float] = {}
    for p in positions:
        atype = p.get("asset_type") or "other"
        asset_groups[atype] = asset_groups.get(atype, 0) + (p.get("market_value") or 0)

    if asset_groups:
        asset_fig = px.pie(
            names=list(asset_groups.keys()),
            values=list(asset_groups.values()),
            hole=0.5,
        )
        asset_fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=220,
                                showlegend=True)
    else:
        asset_fig = go.Figure()
        asset_fig.update_layout(
            annotations=[{"text": "No positions", "showarrow": False}],
            height=220, margin=dict(t=10, b=10, l=10, r=10),
        )

    # Sector allocation donut
    sector_groups: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector") or "Unknown"
        sector_groups[sector] = sector_groups.get(sector, 0) + (
            p.get("market_value") or 0
        )

    if sector_groups:
        sector_fig = px.pie(
            names=list(sector_groups.keys()),
            values=list(sector_groups.values()),
            hole=0.5,
        )
        sector_fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=220,
                                 showlegend=True)
    else:
        sector_fig = go.Figure()
        sector_fig.update_layout(
            annotations=[{"text": "No data", "showarrow": False}],
            height=220, margin=dict(t=10, b=10, l=10, r=10),
        )

    return cards, table_data, asset_fig, sector_fig


@callback(
    Output("dash-portfolio-chart", "figure"),
    Input("dash-range-1m", "n_clicks"),
    Input("dash-range-3m", "n_clicks"),
    Input("dash-range-6m", "n_clicks"),
    Input("dash-range-ytd", "n_clicks"),
    Input("dash-range-1y", "n_clicks"),
    Input("dash-range-all", "n_clicks"),
    Input("dash-account-filter", "value"),
)
def update_portfolio_chart(n1, n3, n6, nytd, n1y, nall, account_id):
    """Update the portfolio value line chart based on time range."""
    import dash

    # Determine which button was clicked
    ctx = dash.ctx
    days = 365  # default
    if ctx.triggered_id == "dash-range-1m":
        days = 30
    elif ctx.triggered_id == "dash-range-3m":
        days = 90
    elif ctx.triggered_id == "dash-range-6m":
        days = 180
    elif ctx.triggered_id == "dash-range-ytd":
        days = None  # handled separately
    elif ctx.triggered_id == "dash-range-all":
        days = 99999

    snapshots = get_snapshots(account_id, days)

    if not snapshots:
        fig = go.Figure()
        fig.update_layout(
            annotations=[{"text": "No snapshot data yet — sync from IBKR first",
                          "showarrow": False}],
            height=300,
        )
        return fig

    import pandas as pd
    df = pd.DataFrame(snapshots)
    fig = px.line(df, x="date", y="total_value",
                  labels={"date": "Date", "total_value": "Portfolio Value"})
    fig.update_layout(height=300, margin=dict(t=10, b=40, l=60, r=10))
    fig.update_traces(line_color="#2c7be5")
    return fig
