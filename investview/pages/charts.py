"""Charts page — interactive price charting with overlays and comparisons."""

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, callback, Output, Input, State
from plotly.subplots import make_subplots

from data.market_data import (
    get_price_history, get_ticker_info, calculate_moving_averages,
)
from db.database import get_positions, get_watchlist
from utils.formatting import fmt_currency, fmt_large_number, fmt_pct

dash.register_page(__name__, path="/charts", name="Charts")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PERIOD_MAP = {
    "1D": "1d", "5D": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo",
    "YTD": "ytd", "1Y": "1y", "5Y": "5y", "MAX": "max",
}

_INTERVAL_MAP = {
    "1D": "5m", "5D": "15m", "1M": "1d", "3M": "1d", "6M": "1d",
    "YTD": "1d", "1Y": "1d", "5Y": "1wk", "MAX": "1mo",
}


def _build_ticker_options() -> list[dict]:
    """Build dropdown options from holdings + watchlist."""
    options = []
    seen = set()
    for p in get_positions():
        t = p.get("ticker", "")
        if t and t not in seen:
            options.append({"label": t, "value": t})
            seen.add(t)
    for w in get_watchlist():
        t = w.get("ticker", "")
        if t and t not in seen:
            options.append({"label": t, "value": t})
            seen.add(t)
    return sorted(options, key=lambda o: o["label"])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container([
    html.H4("Price Charts", className="mb-3"),

    # Ticker input & controls
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(id="chart-ticker", placeholder="Enter ticker...",
                         options=[], searchable=True, clearable=False),
            md=3,
        ),
        dbc.Col(
            dbc.ButtonGroup([
                dbc.Button(label, id=f"chart-range-{label}", size="sm",
                           outline=True, color="primary",
                           active=(label == "1Y"))
                for label in _PERIOD_MAP
            ]),
            md=6,
        ),
        dbc.Col(
            dbc.RadioItems(
                id="chart-type",
                options=[
                    {"label": "Line", "value": "line"},
                    {"label": "Candlestick", "value": "candle"},
                ],
                value="line",
                inline=True,
            ),
            md=3,
        ),
    ], className="mb-2"),

    # Overlay checkboxes
    dbc.Row(
        dbc.Col(
            dbc.Checklist(
                id="chart-overlays",
                options=[
                    {"label": "50-day MA", "value": "50"},
                    {"label": "200-day MA", "value": "200"},
                ],
                value=[],
                inline=True,
            ),
            md=6,
        ),
        className="mb-2",
    ),

    # Comparison tickers
    dbc.Row([
        dbc.Col(html.Small("Compare with:"), width="auto",
                className="align-self-center"),
        dbc.Col(dbc.Input(id="chart-compare-1", placeholder="Ticker",
                          size="sm"), md=2),
        dbc.Col(dbc.Input(id="chart-compare-2", placeholder="Ticker",
                          size="sm"), md=2),
        dbc.Col(dbc.Input(id="chart-compare-3", placeholder="Ticker",
                          size="sm"), md=2),
    ], className="mb-3"),

    # Main chart
    dcc.Loading(dcc.Graph(id="chart-main", style={"height": "500px"})),

    # Stats panel
    html.Hr(),
    dbc.Row(id="chart-stats", className="g-3"),
], fluid=True)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("chart-ticker", "options"),
    Input("chart-ticker", "search_value"),
)
def refresh_ticker_options(search):
    """Refresh ticker dropdown options."""
    options = _build_ticker_options()
    # If user types something not in the list, allow it as a custom option
    if search and search.upper() not in {o["value"] for o in options}:
        options.insert(0, {"label": search.upper(), "value": search.upper()})
    return options


@callback(
    Output("chart-main", "figure"),
    Input("chart-ticker", "value"),
    *[Input(f"chart-range-{label}", "n_clicks") for label in _PERIOD_MAP],
    Input("chart-type", "value"),
    Input("chart-overlays", "value"),
    Input("chart-compare-1", "value"),
    Input("chart-compare-2", "value"),
    Input("chart-compare-3", "value"),
)
def update_chart(ticker, *args):
    """Build the price chart based on current selections."""
    # Unpack args: range button clicks, chart_type, overlays, compare tickers
    n_range_buttons = len(_PERIOD_MAP)
    chart_type = args[n_range_buttons]
    overlays = args[n_range_buttons + 1] or []
    compare_tickers = [
        t.upper().strip() for t in args[n_range_buttons + 2: n_range_buttons + 5]
        if t and t.strip()
    ]

    if not ticker:
        fig = go.Figure()
        fig.update_layout(
            annotations=[{"text": "Select a ticker to begin", "showarrow": False}],
            height=500,
        )
        return fig

    # Determine selected time range from context
    ctx = dash.ctx
    period_label = "1Y"
    for label in _PERIOD_MAP:
        if ctx.triggered_id == f"chart-range-{label}":
            period_label = label
            break

    period = _PERIOD_MAP[period_label]
    interval = _INTERVAL_MAP[period_label]

    df = get_price_history(ticker, period=period, interval=interval)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            annotations=[{"text": f"No data for {ticker}", "showarrow": False}],
            height=500,
        )
        return fig

    # Build figure with volume subplot
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # Price trace
    if chart_type == "candle" and all(
        c in df.columns for c in ["Open", "High", "Low", "Close"]
    ):
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name=ticker,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], mode="lines", name=ticker,
            line=dict(color="#2c7be5"),
        ), row=1, col=1)

    # Moving averages
    if overlays and "Close" in df.columns:
        windows = [int(o) for o in overlays]
        df = calculate_moving_averages(df, windows)
        ma_colors = {"50": "#e67e22", "200": "#e74c3c"}
        for w in overlays:
            col = f"MA_{w}"
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col], mode="lines",
                    name=f"{w}-day MA",
                    line=dict(color=ma_colors.get(w, "gray"), dash="dash"),
                ), row=1, col=1)

    # Volume bars
    if "Volume" in df.columns:
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"], name="Volume",
            marker_color="rgba(44,123,229,0.3)",
        ), row=2, col=1)

    # Comparison overlays (normalised % change)
    for comp in compare_tickers:
        comp_df = get_price_history(comp, period=period, interval=interval)
        if not comp_df.empty and "Close" in comp_df.columns:
            # Normalise both to % change from first value
            base_start = df["Close"].iloc[0]
            comp_start = comp_df["Close"].iloc[0]
            if base_start and comp_start:
                fig.add_trace(go.Scatter(
                    x=comp_df.index,
                    y=(comp_df["Close"] / comp_start - 1) * 100,
                    mode="lines", name=comp, yaxis="y3",
                ), row=1, col=1)

    fig.update_layout(
        height=500,
        margin=dict(t=30, b=30, l=60, r=10),
        showlegend=True,
        legend=dict(orientation="h", y=1.02),
        xaxis_rangeslider_visible=False,
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


@callback(
    Output("chart-stats", "children"),
    Input("chart-ticker", "value"),
)
def update_stats(ticker):
    """Show stats panel for the selected ticker."""
    if not ticker:
        return []

    info = get_ticker_info(ticker)
    if not info:
        return [dbc.Col(html.P("Ticker info unavailable", className="text-muted"))]

    items = [
        ("Current Price", fmt_currency(info.get("pe_ratio") and None)),
        ("52-Wk High", fmt_currency(info.get("fifty_two_week_high"))),
        ("52-Wk Low", fmt_currency(info.get("fifty_two_week_low"))),
        ("Market Cap", fmt_large_number(info.get("market_cap"))),
        ("P/E Ratio", f"{info['pe_ratio']:.2f}" if info.get("pe_ratio") else "N/A"),
        ("Div Yield",
         fmt_pct(info["dividend_yield"] * 100)
         if info.get("dividend_yield") else "N/A"),
        ("Avg Volume", fmt_large_number(info.get("avg_volume"))),
        ("Sector", info.get("sector") or "N/A"),
    ]

    return [
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Small(label, className="text-muted d-block"),
                html.Span(value, className="fw-bold"),
            ]), className="shadow-sm"),
            md=3, sm=6, className="mb-2",
        )
        for label, value in items
    ]
