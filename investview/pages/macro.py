"""Macro page — FRED economic data dashboard."""

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc, callback, Output, Input

from components.cards import metric_card
from data.macro_data import (
    is_available, get_fed_funds_rate, get_treasury_yields,
    get_yield_curve, get_cpi, get_unemployment, get_series,
)
from utils.formatting import fmt_pct

dash.register_page(__name__, path="/macro", name="Macro")

# Preset FRED series for the time-series dropdown
_SERIES_PRESETS = {
    "Fed Funds Rate": "DFF",
    "CPI (All Urban)": "CPIAUCSL",
    "Unemployment Rate": "UNRATE",
    "Real GDP": "GDPC1",
    "S&P 500": "SP500",
    "10Y Treasury": "DGS10",
    "2Y Treasury": "DGS2",
}

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = dbc.Container([
    html.H4("Macro / Economic Data", className="mb-3"),

    # FRED availability warning
    dbc.Alert(
        "FRED API key not configured. Add FRED_API_KEY to your .env file "
        "to enable macroeconomic data.",
        id="macro-api-warning",
        color="warning",
        is_open=False,
        dismissable=True,
    ),

    # Key rates cards
    dbc.Row(id="macro-rate-cards", className="mb-4 g-3"),

    # Yield curve chart
    dbc.Row([
        dbc.Col([
            html.H5("Yield Curve"),
            dcc.Graph(id="macro-yield-curve"),
        ], md=6),
        dbc.Col([
            html.H5("Time Series"),
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id="macro-series-select",
                        options=[{"label": k, "value": v}
                                 for k, v in _SERIES_PRESETS.items()],
                        value="DFF",
                        clearable=False,
                    ),
                    md=6,
                ),
                dbc.Col(
                    dcc.Dropdown(
                        id="macro-series-range",
                        options=[
                            {"label": "1 Year", "value": "1"},
                            {"label": "5 Years", "value": "5"},
                            {"label": "10 Years", "value": "10"},
                            {"label": "20 Years", "value": "20"},
                            {"label": "All", "value": "all"},
                        ],
                        value="5",
                        clearable=False,
                    ),
                    md=4,
                ),
                dbc.Col(
                    dbc.Button("Refresh", id="macro-refresh-btn", size="sm",
                               color="primary"),
                    md=2, className="d-grid",
                ),
            ], className="mb-2"),
            dcc.Graph(id="macro-series-chart"),
        ], md=6),
    ]),
], fluid=True)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("macro-api-warning", "is_open"),
    Output("macro-rate-cards", "children"),
    Output("macro-yield-curve", "figure"),
    Input("macro-refresh-btn", "n_clicks"),
)
def update_macro_dashboard(_n):
    """Refresh all macro data panels."""
    if not is_available():
        empty = go.Figure()
        empty.update_layout(
            annotations=[{"text": "FRED API key required", "showarrow": False}],
            height=300,
        )
        return True, [], empty

    # Key rates
    ff_rate = get_fed_funds_rate()
    yields = get_treasury_yields()
    cpi = get_cpi()
    unemp = get_unemployment()
    spread_2_10 = None
    if yields.get("10Y") is not None and yields.get("2Y") is not None:
        spread_2_10 = yields["10Y"] - yields["2Y"]

    cards = dbc.Row([
        dbc.Col(metric_card("Fed Funds Rate",
                            fmt_pct(ff_rate) if ff_rate else "N/A"), md=2),
        dbc.Col(metric_card("10Y Treasury",
                            fmt_pct(yields.get("10Y"))), md=2),
        dbc.Col(metric_card("2Y Treasury",
                            fmt_pct(yields.get("2Y"))), md=2),
        dbc.Col(metric_card("2Y/10Y Spread",
                            fmt_pct(spread_2_10)), md=2),
        dbc.Col(metric_card("CPI YoY",
                            fmt_pct(cpi.get("yoy_change"))), md=2),
        dbc.Col(metric_card("Unemployment",
                            fmt_pct(unemp) if unemp else "N/A"), md=2),
    ], className="g-3")

    # Yield curve
    yc_df = get_yield_curve()
    if not yc_df.empty and yc_df["yield"].notna().any():
        yc_fig = px.line(
            yc_df.dropna(subset=["yield"]),
            x="maturity", y="yield",
            markers=True,
            labels={"maturity": "Maturity", "yield": "Yield (%)"},
        )
        yc_fig.update_layout(height=300, margin=dict(t=10, b=40, l=50, r=10))
    else:
        yc_fig = go.Figure()
        yc_fig.update_layout(
            annotations=[{"text": "Yield curve data unavailable",
                          "showarrow": False}],
            height=300,
        )

    return False, cards, yc_fig


@callback(
    Output("macro-series-chart", "figure"),
    Input("macro-series-select", "value"),
    Input("macro-series-range", "value"),
    Input("macro-refresh-btn", "n_clicks"),
)
def update_series_chart(series_id, range_years, _n):
    """Update the time series chart."""
    if not is_available() or not series_id:
        fig = go.Figure()
        fig.update_layout(height=300)
        return fig

    from datetime import datetime, timedelta

    start = None
    if range_years != "all":
        years = int(range_years)
        start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")

    data = get_series(series_id, start_date=start)
    if data.empty:
        fig = go.Figure()
        fig.update_layout(
            annotations=[{"text": "No data", "showarrow": False}],
            height=300,
        )
        return fig

    # Find the human-readable name
    name = series_id
    for label, sid in _SERIES_PRESETS.items():
        if sid == series_id:
            name = label
            break

    fig = px.line(x=data.index, y=data.values,
                  labels={"x": "Date", "y": name})
    fig.update_layout(height=300, margin=dict(t=10, b=40, l=50, r=10))
    return fig
