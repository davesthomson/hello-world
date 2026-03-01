"""Positions page — full positions table with filtering and detail panel."""

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, callback, Output, Input, State, dash_table

from components.tables import pnl_conditional_styles, DEFAULT_TABLE_STYLE
from data.market_data import get_price_history, get_ticker_info
from db.database import get_positions, get_accounts
from utils.formatting import fmt_currency, fmt_pct

dash.register_page(__name__, path="/positions", name="Positions")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container([
    html.H4("Positions", className="mb-3"),

    # Filter bar
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(id="pos-account-filter", placeholder="All Accounts",
                         clearable=True),
            md=3,
        ),
        dbc.Col(
            dcc.Dropdown(
                id="pos-asset-type-filter",
                options=[
                    {"label": "Stock", "value": "stock"},
                    {"label": "ETF", "value": "etf"},
                    {"label": "Option", "value": "option"},
                    {"label": "Bond", "value": "bond"},
                    {"label": "Cash", "value": "cash"},
                ],
                placeholder="All Asset Types",
                clearable=True,
            ),
            md=3,
        ),
        dbc.Col(
            dbc.Input(id="pos-ticker-search", placeholder="Search ticker...",
                      type="text", debounce=True),
            md=3,
        ),
    ], className="mb-3"),

    # Positions DataTable
    dash_table.DataTable(
        id="pos-table",
        columns=[
            {"name": "Ticker", "id": "ticker"},
            {"name": "Name", "id": "name"},
            {"name": "Shares", "id": "quantity", "type": "numeric",
             "format": {"specifier": ",.2f"}},
            {"name": "Avg Cost", "id": "avg_cost_basis", "type": "numeric",
             "format": {"specifier": "$,.2f"}},
            {"name": "Price", "id": "current_price", "type": "numeric",
             "format": {"specifier": "$,.2f"}},
            {"name": "Mkt Value", "id": "market_value", "type": "numeric",
             "format": {"specifier": "$,.0f"}},
            {"name": "P&L $", "id": "unrealized_pnl", "type": "numeric",
             "format": {"specifier": "$,.2f"}},
            {"name": "P&L %", "id": "unrealized_pnl_pct", "type": "numeric",
             "format": {"specifier": "+.2f"}},
            {"name": "Sector", "id": "sector"},
            {"name": "Type", "id": "asset_type"},
        ],
        sort_action="native",
        row_selectable="single",
        page_size=25,
        style_cell_conditional=[
            {"if": {"column_id": "ticker"}, "textAlign": "left"},
            {"if": {"column_id": "name"}, "textAlign": "left"},
            {"if": {"column_id": "sector"}, "textAlign": "left"},
            {"if": {"column_id": "asset_type"}, "textAlign": "left"},
        ],
        style_data_conditional=(
            DEFAULT_TABLE_STYLE["style_data_conditional"]
            + pnl_conditional_styles("unrealized_pnl")
            + pnl_conditional_styles("unrealized_pnl_pct")
        ),
        **(DEFAULT_TABLE_STYLE),
    ),

    # Summary row
    html.Div(id="pos-summary", className="mt-2 fw-bold"),

    # Detail panel (shown when a row is clicked)
    html.Hr(),
    dbc.Collapse(
        dbc.Card(dbc.CardBody(id="pos-detail-body"), className="shadow-sm"),
        id="pos-detail-collapse",
        is_open=False,
    ),
], fluid=True)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("pos-account-filter", "options"),
    Input("pos-ticker-search", "value"),  # just a trigger on page load
)
def load_accounts(_):
    accounts = get_accounts()
    return [{"label": a["name"], "value": a["id"]} for a in accounts]


@callback(
    Output("pos-table", "data"),
    Output("pos-summary", "children"),
    Input("pos-account-filter", "value"),
    Input("pos-asset-type-filter", "value"),
    Input("pos-ticker-search", "value"),
)
def update_positions_table(account_id, asset_type, ticker_search):
    """Filter and display positions."""
    positions = get_positions(account_id)

    if asset_type:
        positions = [p for p in positions if p.get("asset_type") == asset_type]
    if ticker_search:
        q = ticker_search.upper()
        positions = [
            p for p in positions
            if q in (p.get("ticker") or "").upper()
            or q in (p.get("name") or "").upper()
        ]

    total_mv = sum(p.get("market_value") or 0 for p in positions)
    total_pnl = sum(p.get("unrealized_pnl") or 0 for p in positions)

    summary = (
        f"Total Market Value: {fmt_currency(total_mv)}  |  "
        f"Total Unrealized P&L: {fmt_currency(total_pnl)}"
    )

    return positions, summary


@callback(
    Output("pos-detail-collapse", "is_open"),
    Output("pos-detail-body", "children"),
    Input("pos-table", "selected_rows"),
    State("pos-table", "data"),
)
def show_position_detail(selected_rows, data):
    """Show a detail panel when a row is clicked."""
    if not selected_rows or not data:
        return False, ""

    row = data[selected_rows[0]]
    ticker = row.get("ticker", "")

    # Get ticker info and mini chart
    info = get_ticker_info(ticker)
    df = get_price_history(ticker, period="1mo")

    # Mini chart
    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], mode="lines", name=ticker,
            line=dict(color="#2c7be5"),
        ))
        fig.update_layout(height=200, margin=dict(t=10, b=30, l=40, r=10),
                          showlegend=False)
        chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    else:
        chart = html.P("Chart data unavailable", className="text-muted")

    detail = dbc.Row([
        dbc.Col([
            html.H5(f"{ticker} — {info.get('name', '')}"),
            html.P(f"Sector: {info.get('sector', 'N/A')}"),
            html.P(f"Market Cap: {info.get('market_cap', 'N/A')}"),
            html.P(f"P/E: {info.get('pe_ratio', 'N/A')}"),
            html.P(f"Div Yield: {info.get('dividend_yield', 'N/A')}"),
            dbc.Button("Open Full Chart", href=f"/charts?ticker={ticker}",
                       color="primary", size="sm", className="mt-2"),
        ], md=4),
        dbc.Col(chart, md=8),
    ])

    return True, detail
