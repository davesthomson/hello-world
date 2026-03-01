"""Dashboard — Portfolio overview / home page."""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import pandas as pd

from db.database import get_accounts, get_positions, get_snapshots, refresh_position_prices
from data.macro_data import get_fed_funds_rate, get_treasury_yields, get_cpi
from utils.formatting import fmt_currency, fmt_pct, pnl_color, pnl_arrow
from config import logger

conn = st.session_state.db_conn

# ---------------------------------------------------------------------------
# Macro sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Macro Indicators")
    try:
        fed_rate = get_fed_funds_rate()
        t10y = get_treasury_yields("10y")
        cpi = get_cpi()

        if fed_rate is not None:
            st.metric("Fed Funds Rate", f"{fed_rate:.2f}%")
        else:
            st.metric("Fed Funds Rate", "N/A")

        if t10y is not None:
            st.metric("10Y Treasury", f"{t10y:.2f}%")
        else:
            st.metric("10Y Treasury", "N/A")

        if cpi is not None:
            cpi_label = f"{cpi['latest']:.1f}"
            cpi_delta = f"{cpi['yoy_change']:.1f}% YoY" if cpi.get("yoy_change") is not None else None
            st.metric("CPI", cpi_label, delta=cpi_delta)
        else:
            st.metric("CPI", "N/A")
    except Exception as e:
        st.warning(f"Could not load macro data: {e}")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.title("Portfolio Dashboard")

accounts = get_accounts(conn)

if not accounts:
    st.info("No accounts found. Go to **Import & Sync** to add an account and import data.")
    st.stop()

# Refresh prices button
if st.button("Refresh Prices (yfinance)"):
    with st.spinner("Fetching latest prices from yfinance..."):
        updated = refresh_position_prices(conn)
        if updated:
            st.success(f"Updated prices for {updated} positions.")
        else:
            st.info("No equity positions to update.")

all_positions = get_positions(conn)

# ---------------------------------------------------------------------------
# Header metrics
# ---------------------------------------------------------------------------
total_value = sum(p["market_value"] or 0 for p in all_positions)
total_pnl = sum(p["unrealized_pnl"] or 0 for p in all_positions)
total_cost = sum((p["avg_cost_basis"] or 0) * (p["quantity"] or 0) for p in all_positions)
total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Portfolio Value", fmt_currency(total_value))
col2.metric("Unrealized P&L", fmt_currency(total_pnl), delta=fmt_pct(total_pnl_pct))
col3.metric("Positions", str(len(all_positions)))

st.divider()

# ---------------------------------------------------------------------------
# Account cards
# ---------------------------------------------------------------------------
st.subheader("Accounts")
acct_cols = st.columns(min(len(accounts), 4))
for i, acct in enumerate(accounts):
    with acct_cols[i % len(acct_cols)]:
        acct_positions = [p for p in all_positions if p["account_id"] == acct["id"]]
        acct_value = sum(p["market_value"] or 0 for p in acct_positions)
        acct_pnl = sum(p["unrealized_pnl"] or 0 for p in acct_positions)

        st.markdown(f"**{acct['name']}**")
        st.caption(f"{acct['broker'].upper()} — {acct['account_number'] or 'N/A'}")
        st.metric("Value", fmt_currency(acct_value), delta=fmt_currency(acct_pnl))

st.divider()

# ---------------------------------------------------------------------------
# Top holdings table (uses DB data only — no Yahoo API calls on page load)
# ---------------------------------------------------------------------------
st.subheader("Top Holdings")
if all_positions:
    top = sorted(all_positions, key=lambda p: p["market_value"] or 0, reverse=True)[:10]

    rows = []
    for p in top:
        rows.append({
            "Ticker": p["ticker"],
            "Shares": f"{p['quantity']:,.2f}",
            "Price": fmt_currency(p["current_price"]),
            "Market Value": fmt_currency(p["market_value"]),
            "P&L": fmt_currency(p["unrealized_pnl"]),
            "P&L %": fmt_pct(p["unrealized_pnl_pct"]),
            "Account": p["account_name"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No positions to display.")

# ---------------------------------------------------------------------------
# Allocation charts (asset type from DB — no Yahoo calls needed)
# ---------------------------------------------------------------------------
if all_positions:
    chart_col1, chart_col2 = st.columns(2)

    # Asset allocation donut
    with chart_col1:
        st.subheader("Asset Allocation")
        asset_data: dict[str, float] = {}
        for p in all_positions:
            atype = p["asset_type"] or "stock"
            asset_data[atype] = asset_data.get(atype, 0) + (p["market_value"] or 0)

        if asset_data:
            fig = px.pie(
                names=list(asset_data.keys()),
                values=list(asset_data.values()),
                hole=0.4,
                title="By Asset Type",
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Portfolio value over time
# ---------------------------------------------------------------------------
snapshots = get_snapshots(conn, account_id=None)
if snapshots:
    st.subheader("Portfolio Value Over Time")
    snap_df = pd.DataFrame([dict(s) for s in snapshots])
    snap_df["date"] = pd.to_datetime(snap_df["date"])
    fig = px.line(snap_df, x="date", y="total_value", title="Total Portfolio Value")
    fig.update_layout(xaxis_title="Date", yaxis_title="Value ($)")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("InvestView Phase 1 — Last page load: " + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
