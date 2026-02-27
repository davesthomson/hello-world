"""Charts — Interactive price charting page."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from db.database import get_watchlist, get_positions, is_equity_ticker, yfinance_ticker
from data.market_data import get_price_history, get_ticker_info
from utils.formatting import fmt_currency, fmt_large_number, fmt_pct
from config import logger


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_ticker_info(ticker: str) -> dict:
    """Fetch ticker info with 1-hour Streamlit cache to avoid Yahoo rate limits."""
    return get_ticker_info(ticker)

conn = st.session_state.db_conn

st.title("Price Charts")

# ---------------------------------------------------------------------------
# Ticker input with suggestions from watchlist + holdings
# ---------------------------------------------------------------------------
watchlist = get_watchlist(conn)
positions = get_positions(conn)
suggestions = sorted(set(
    yfinance_ticker(p["ticker"], p["exchange"]) for p in positions
    if is_equity_ticker(p["ticker"])
) | set(
    yfinance_ticker(w["ticker"]) for w in watchlist
    if is_equity_ticker(w["ticker"])
))

col_input, col_period, col_type = st.columns([2, 2, 1])

with col_input:
    ticker_input = yfinance_ticker(st.text_input(
        "Ticker",
        value=suggestions[0] if suggestions else "SPY",
        placeholder="Enter ticker symbol",
    ).upper().strip())
    if suggestions:
        st.caption(f"Suggestions: {', '.join(suggestions[:10])}")

# Period mapping
PERIOD_MAP = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "MAX": ("max", "1mo"),
}

with col_period:
    period_label = st.selectbox("Time Range", list(PERIOD_MAP.keys()), index=6)  # default 1Y
    period, interval = PERIOD_MAP[period_label]

with col_type:
    chart_type = st.radio("Chart Type", ["Line", "Candlestick"], horizontal=True)

# ---------------------------------------------------------------------------
# Overlay options
# ---------------------------------------------------------------------------
overlay_col1, overlay_col2 = st.columns(2)
with overlay_col1:
    show_50ma = st.checkbox("50-day MA", value=True)
    show_200ma = st.checkbox("200-day MA", value=False)

with overlay_col2:
    compare_tickers = st.text_input(
        "Compare (up to 3 tickers, comma-separated)",
        placeholder="e.g. QQQ, DIA",
    )
    compare_list = [
        t.strip().upper()
        for t in compare_tickers.split(",")
        if t.strip()
    ][:3]

# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------
if not ticker_input:
    st.warning("Enter a ticker symbol to display a chart.")
    st.stop()

hist = get_price_history(ticker_input, period=period, interval=interval, conn=conn)

if hist.empty:
    st.error(f"No data available for {ticker_input}. Check the ticker symbol.")
    st.stop()

# ---------------------------------------------------------------------------
# Build chart
# ---------------------------------------------------------------------------
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=[0.75, 0.25],
    subplot_titles=(f"{ticker_input} — {period_label}", "Volume"),
)

if chart_type == "Candlestick":
    fig.add_trace(
        go.Candlestick(
            x=hist.index,
            open=hist["Open"],
            high=hist["High"],
            low=hist["Low"],
            close=hist["Close"],
            name=ticker_input,
        ),
        row=1,
        col=1,
    )
else:
    fig.add_trace(
        go.Scatter(
            x=hist.index,
            y=hist["Close"],
            name=ticker_input,
            mode="lines",
            line=dict(color="#1f77b4", width=2),
        ),
        row=1,
        col=1,
    )

# Moving averages
if show_50ma and len(hist) >= 50:
    ma50 = hist["Close"].rolling(window=50).mean()
    fig.add_trace(
        go.Scatter(
            x=hist.index,
            y=ma50,
            name="50-day MA",
            line=dict(color="orange", width=1, dash="dash"),
        ),
        row=1,
        col=1,
    )

if show_200ma and len(hist) >= 200:
    ma200 = hist["Close"].rolling(window=200).mean()
    fig.add_trace(
        go.Scatter(
            x=hist.index,
            y=ma200,
            name="200-day MA",
            line=dict(color="red", width=1, dash="dash"),
        ),
        row=1,
        col=1,
    )

# Volume subplot
if "Volume" in hist.columns:
    colors = [
        "green" if hist["Close"].iloc[i] >= hist["Open"].iloc[i] else "red"
        for i in range(len(hist))
    ]
    fig.add_trace(
        go.Bar(
            x=hist.index,
            y=hist["Volume"],
            name="Volume",
            marker_color=colors,
            opacity=0.5,
        ),
        row=2,
        col=1,
    )

fig.update_layout(
    height=600,
    xaxis_rangeslider_visible=False,
    showlegend=True,
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
)
fig.update_yaxes(title_text="Price", row=1, col=1)
fig.update_yaxes(title_text="Volume", row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Comparison overlay (normalized to % change)
# ---------------------------------------------------------------------------
if compare_list:
    st.subheader("Comparison")
    comp_fig = go.Figure()

    # Normalize main ticker
    base_close = hist["Close"]
    if len(base_close) > 0:
        base_start = base_close.iloc[0]
        if base_start and base_start != 0:
            norm = ((base_close - base_start) / base_start) * 100
            comp_fig.add_trace(
                go.Scatter(x=hist.index, y=norm, name=ticker_input, mode="lines")
            )

    colors = ["#ff7f0e", "#2ca02c", "#d62728"]
    for i, comp_ticker in enumerate(compare_list):
        comp_hist = get_price_history(comp_ticker, period=period, interval=interval, conn=conn)
        if not comp_hist.empty:
            comp_close = comp_hist["Close"]
            comp_start = comp_close.iloc[0]
            if comp_start and comp_start != 0:
                comp_norm = ((comp_close - comp_start) / comp_start) * 100
                comp_fig.add_trace(
                    go.Scatter(
                        x=comp_hist.index,
                        y=comp_norm,
                        name=comp_ticker,
                        mode="lines",
                        line=dict(color=colors[i % len(colors)]),
                    )
                )
        else:
            st.warning(f"No data for {comp_ticker}")

    comp_fig.update_layout(
        title="Relative Performance (% Change)",
        yaxis_title="% Change",
        height=400,
    )
    st.plotly_chart(comp_fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Key stats card
# ---------------------------------------------------------------------------
st.subheader(f"Key Stats — {ticker_input}")
info = _cached_ticker_info(ticker_input)

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

with stat_col1:
    current_price = hist["Close"].iloc[-1] if len(hist) > 0 else None
    st.metric("Current Price", fmt_currency(current_price))
    if info.get("fifty_two_week_high") and info.get("fifty_two_week_low"):
        st.write(f"52W Range: {fmt_currency(info['fifty_two_week_low'])} — {fmt_currency(info['fifty_two_week_high'])}")

with stat_col2:
    if info.get("market_cap"):
        st.metric("Market Cap", f"${fmt_large_number(info['market_cap'])}")
    if info.get("pe_ratio"):
        st.metric("P/E Ratio", f"{info['pe_ratio']:.2f}")

with stat_col3:
    if info.get("dividend_yield") is not None:
        st.metric("Dividend Yield", f"{info['dividend_yield'] * 100:.2f}%")
    if info.get("beta") is not None:
        st.metric("Beta", f"{info['beta']:.2f}")

with stat_col4:
    if info.get("avg_volume"):
        st.metric("Avg Volume", fmt_large_number(info["avg_volume"]))
    st.write(f"Sector: {info.get('sector', 'N/A')}")
