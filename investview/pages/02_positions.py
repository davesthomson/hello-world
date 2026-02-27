"""Positions — Detailed view of all positions with filtering."""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import pandas as pd

from db.database import get_accounts, get_positions, refresh_position_prices
from data.market_data import get_ticker_info, get_price_history
from utils.formatting import fmt_currency, fmt_pct
from config import logger

conn = st.session_state.db_conn

st.title("Positions")

if st.button("Refresh Prices (yfinance)"):
    with st.spinner("Fetching latest prices from yfinance..."):
        updated = refresh_position_prices(conn)
        if updated:
            st.success(f"Updated prices for {updated} positions.")
        else:
            st.info("No equity positions to update.")

# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------
accounts = get_accounts(conn)
acct_names = {a["id"]: a["name"] for a in accounts}

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    selected_accounts = st.multiselect(
        "Accounts",
        options=[a["id"] for a in accounts],
        format_func=lambda x: acct_names.get(x, str(x)),
        default=[a["id"] for a in accounts],
    )

with filter_col2:
    asset_types = ["All", "stock", "etf", "option", "bond", "cash"]
    selected_asset_type = st.selectbox("Asset Type", asset_types)

with filter_col3:
    search_ticker = st.text_input("Search Ticker", placeholder="e.g. AAPL").upper().strip()

# ---------------------------------------------------------------------------
# Fetch and filter positions
# ---------------------------------------------------------------------------
all_positions = []
for acct_id in selected_accounts:
    asset_filter = selected_asset_type if selected_asset_type != "All" else None
    positions = get_positions(conn, account_id=acct_id, asset_type=asset_filter)
    all_positions.extend(positions)

if search_ticker:
    all_positions = [p for p in all_positions if search_ticker in p["ticker"]]

if not all_positions:
    st.info("No positions match the current filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Build display table
# ---------------------------------------------------------------------------
tickers = list({p["ticker"] for p in all_positions})
ticker_info_cache: dict[str, dict] = {}
for t in tickers:
    try:
        ticker_info_cache[t] = get_ticker_info(t)
    except Exception:
        ticker_info_cache[t] = {"name": t, "sector": "N/A"}

rows = []
for p in all_positions:
    info = ticker_info_cache.get(p["ticker"], {})
    rows.append({
        "Ticker": p["ticker"],
        "Name": info.get("name", p["ticker"]),
        "Account": p["account_name"],
        "Type": p["asset_type"],
        "Shares": p["quantity"],
        "Avg Cost": p["avg_cost_basis"],
        "Price": p["current_price"],
        "Market Value": p["market_value"],
        "P&L ($)": p["unrealized_pnl"],
        "P&L (%)": p["unrealized_pnl_pct"],
        "Sector": info.get("sector", "N/A"),
    })

df = pd.DataFrame(rows)

# Totals row
totals = {
    "Ticker": "TOTAL",
    "Name": "",
    "Account": "",
    "Type": "",
    "Shares": "",
    "Avg Cost": "",
    "Price": "",
    "Market Value": df["Market Value"].sum(),
    "P&L ($)": df["P&L ($)"].sum(),
    "P&L (%)": "",
    "Sector": "",
}
df_with_totals = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)

# Format for display
display_df = df_with_totals.copy()
for col in ["Avg Cost", "Price", "Market Value", "P&L ($)"]:
    display_df[col] = display_df[col].apply(
        lambda x: fmt_currency(x) if isinstance(x, (int, float)) else x
    )
display_df["P&L (%)"] = display_df["P&L (%)"].apply(
    lambda x: fmt_pct(x) if isinstance(x, (int, float)) else x
)
display_df["Shares"] = display_df["Shares"].apply(
    lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else x
)

st.dataframe(display_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Position detail expander
# ---------------------------------------------------------------------------
st.subheader("Position Details")
st.caption("Select a ticker below to see detailed info and a 30-day price chart.")

selected_ticker = st.selectbox(
    "Select Ticker",
    options=tickers,
    index=0 if tickers else None,
)

if selected_ticker:
    with st.expander(f"Details: {selected_ticker}", expanded=True):
        info = ticker_info_cache.get(selected_ticker, {})

        detail_col1, detail_col2 = st.columns(2)
        with detail_col1:
            st.markdown(f"**{info.get('name', selected_ticker)}**")
            st.write(f"Sector: {info.get('sector', 'N/A')}")
            st.write(f"Industry: {info.get('industry', 'N/A')}")
            if info.get("market_cap"):
                from utils.formatting import fmt_large_number
                st.write(f"Market Cap: ${fmt_large_number(info['market_cap'])}")
            if info.get("pe_ratio"):
                st.write(f"P/E Ratio: {info['pe_ratio']:.2f}")
            if info.get("dividend_yield"):
                st.write(f"Dividend Yield: {info['dividend_yield'] * 100:.2f}%")

        with detail_col2:
            # 30-day mini chart
            hist = get_price_history(selected_ticker, period="1mo", interval="1d", conn=conn)
            if not hist.empty:
                fig = px.line(
                    hist,
                    y="Close",
                    title=f"{selected_ticker} — 30 Day",
                )
                fig.update_layout(
                    height=250,
                    showlegend=False,
                    xaxis_title="",
                    yaxis_title="Price",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No price data available for chart.")
