"""Import & Sync — Manage brokerage connections and manual data import."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st
import pandas as pd

from db.database import (
    get_accounts,
    get_positions,
    insert_account,
    insert_trades,
    refresh_position_prices,
    upsert_positions,
    upsert_snapshot,
)
from adapters.ibkr_adapter import IBKRAdapter, is_gateway_running
from adapters.etrade_adapter import ETradeAdapter
from adapters.csv_adapter import CSVAdapter, PRESET_MAPPINGS
from config import logger

conn = st.session_state.db_conn

st.title("Import & Sync")

# ===================================================================
# IBKR Section
# ===================================================================
st.header("Interactive Brokers (IBKR)")

ibkr_running = is_gateway_running()
status_color = "🟢" if ibkr_running else "🔴"
st.markdown(f"**Gateway Status:** {status_color} {'Connected' if ibkr_running else 'Not detected'}")

if not ibkr_running:
    st.info("Start TWS or IB Gateway to enable IBKR sync.")

ibkr_col1, ibkr_col2, ibkr_col3 = st.columns(3)

with ibkr_col1:
    if st.button("Connect to IBKR", disabled=not ibkr_running):
        adapter = IBKRAdapter()
        if adapter.connect():
            st.session_state.ibkr_adapter = adapter
            st.success("Connected to IBKR!")
        else:
            st.error("Failed to connect to IBKR. Check TWS/Gateway settings.")

with ibkr_col2:
    if st.button("Sync Positions", key="ibkr_sync_pos"):
        adapter = st.session_state.ibkr_adapter
        if adapter is None:
            st.warning("Connect to IBKR first.")
        else:
            with st.spinner("Syncing positions from IBKR..."):
                try:
                    # Ensure account exists
                    accounts = get_accounts(conn)
                    ibkr_acct = next((a for a in accounts if a["broker"] == "ibkr"), None)
                    if not ibkr_acct:
                        acct_id = insert_account(conn, "IBKR Main", "ibkr")
                    else:
                        acct_id = ibkr_acct["id"]

                    positions = adapter.get_positions()
                    count = upsert_positions(conn, acct_id, positions)

                    # Fill in missing prices via yfinance
                    refreshed = refresh_position_prices(conn, account_id=acct_id)
                    if refreshed:
                        logger.info("Enriched %d positions with yfinance prices.", refreshed)

                    # Save snapshot (recompute from DB so yfinance prices are included)
                    summary = adapter.get_account_summary()
                    acct_positions = get_positions(conn, account_id=acct_id)
                    total_val = sum(p["market_value"] or 0 for p in acct_positions)

                    if summary:
                        upsert_snapshot(
                            conn,
                            acct_id,
                            date.today().isoformat(),
                            total_val or summary.get("total_value", 0),
                            summary.get("cash_balance", 0),
                            summary.get("invested_value", 0),
                        )
                    elif total_val:
                        upsert_snapshot(conn, acct_id, date.today().isoformat(), total_val)

                    st.success(f"Synced {count} positions from IBKR ({refreshed} priced via yfinance).")
                except Exception as e:
                    st.error(f"IBKR sync failed: {e}")
                    logger.error("IBKR position sync error: %s", e)

with ibkr_col3:
    if st.button("Sync Trade History", key="ibkr_sync_trades"):
        adapter = st.session_state.ibkr_adapter
        if adapter is None:
            st.warning("Connect to IBKR first.")
        else:
            with st.spinner("Syncing trades from IBKR..."):
                try:
                    accounts = get_accounts(conn)
                    ibkr_acct = next((a for a in accounts if a["broker"] == "ibkr"), None)
                    if not ibkr_acct:
                        acct_id = insert_account(conn, "IBKR Main", "ibkr")
                    else:
                        acct_id = ibkr_acct["id"]

                    trades = adapter.get_trade_history()
                    for t in trades:
                        t["account_id"] = acct_id
                    count = insert_trades(conn, trades)
                    st.success(f"Imported {count} trades from IBKR.")
                except Exception as e:
                    st.error(f"IBKR trade sync failed: {e}")
                    logger.error("IBKR trade sync error: %s", e)

st.divider()

# ===================================================================
# E*Trade Section
# ===================================================================
st.header("E*Trade")

etrade_connected = st.session_state.etrade_adapter is not None
etrade_status = "🟢 Authenticated" if etrade_connected else "🔴 Not authenticated"
st.markdown(f"**OAuth Status:** {etrade_status}")

et_col1, et_col2, et_col3 = st.columns(3)

with et_col1:
    if st.button("Authenticate E*Trade"):
        adapter = ETradeAdapter()
        if adapter.connect():
            st.session_state.etrade_adapter = adapter
            st.info("Visit the authorization URL in your browser, then enter the verifier code below.")
            st.code(adapter._authorize_url)
        else:
            st.error("Failed to start E*Trade OAuth. Check your consumer key/secret in .env")

    verifier = st.text_input("OAuth Verifier Code", key="etrade_verifier")
    if verifier and st.button("Submit Verifier"):
        adapter = st.session_state.etrade_adapter
        if adapter and adapter.complete_oauth(verifier):
            st.success("E*Trade authenticated!")
        else:
            st.error("OAuth verification failed.")

with et_col2:
    if st.button("Sync Positions", key="etrade_sync_pos"):
        adapter = st.session_state.etrade_adapter
        if not adapter or not getattr(adapter, "session", None):
            st.warning("Authenticate with E*Trade first.")
        else:
            with st.spinner("Syncing positions from E*Trade..."):
                try:
                    accounts = get_accounts(conn)
                    et_acct = next((a for a in accounts if a["broker"] == "etrade"), None)
                    if not et_acct:
                        acct_id = insert_account(conn, "E*Trade", "etrade")
                    else:
                        acct_id = et_acct["id"]

                    positions = adapter.get_positions()
                    count = upsert_positions(conn, acct_id, positions)
                    summary = adapter.get_account_summary()
                    if summary:
                        upsert_snapshot(
                            conn,
                            acct_id,
                            date.today().isoformat(),
                            summary.get("total_value", 0),
                            summary.get("cash_balance", 0),
                            summary.get("invested_value", 0),
                        )
                    st.success(f"Synced {count} positions from E*Trade.")
                except Exception as e:
                    st.error(f"E*Trade sync failed: {e}")

with et_col3:
    if st.button("Sync Trade History", key="etrade_sync_trades"):
        adapter = st.session_state.etrade_adapter
        if not adapter or not getattr(adapter, "session", None):
            st.warning("Authenticate with E*Trade first.")
        else:
            with st.spinner("Syncing trades from E*Trade..."):
                try:
                    accounts = get_accounts(conn)
                    et_acct = next((a for a in accounts if a["broker"] == "etrade"), None)
                    if not et_acct:
                        acct_id = insert_account(conn, "E*Trade", "etrade")
                    else:
                        acct_id = et_acct["id"]

                    trades = adapter.get_trade_history()
                    for t in trades:
                        t["account_id"] = acct_id
                    count = insert_trades(conn, trades)
                    st.success(f"Imported {count} trades from E*Trade.")
                except Exception as e:
                    st.error(f"E*Trade trade sync failed: {e}")

st.divider()

# ===================================================================
# CSV Import Section
# ===================================================================
st.header("CSV Import")

csv_col1, csv_col2 = st.columns([1, 1])

with csv_col1:
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

    preset_name = st.selectbox(
        "Column Mapping Preset",
        options=["generic", "ibkr_activity", "etrade_export", "Custom"],
    )

with csv_col2:
    # Target account selection
    accounts = get_accounts(conn)
    acct_options = {a["id"]: a["name"] for a in accounts}
    acct_options[0] = "+ Create new account"

    target_acct = st.selectbox(
        "Import into Account",
        options=list(acct_options.keys()),
        format_func=lambda x: acct_options[x],
    )

    if target_acct == 0:
        new_acct_name = st.text_input("New Account Name", value="CSV Import Account")
    else:
        new_acct_name = ""

    import_as = st.radio("Import as", ["Trades", "Positions"], horizontal=True)

# Custom column mapping
custom_mapping: dict[str, str] = {}
if preset_name == "Custom" and uploaded_file is not None:
    st.subheader("Custom Column Mapping")
    # Peek at headers
    uploaded_file.seek(0)
    import csv as csv_mod
    import io

    reader = csv_mod.DictReader(io.TextIOWrapper(uploaded_file, encoding="utf-8"))
    headers = reader.fieldnames or []
    uploaded_file.seek(0)

    our_fields = ["ticker", "quantity", "price", "avg_cost", "trade_date", "side", "fees"]
    map_cols = st.columns(len(our_fields))
    for i, field in enumerate(our_fields):
        with map_cols[i]:
            selected = st.selectbox(
                field,
                options=["(skip)"] + list(headers),
                key=f"map_{field}",
            )
            if selected != "(skip)":
                custom_mapping[selected] = field

# Preview & Import
if uploaded_file is not None:
    uploaded_file.seek(0)
    raw_content = uploaded_file.read().decode("utf-8")

    adapter = CSVAdapter()
    mapping = custom_mapping if preset_name == "Custom" else None
    preset = preset_name if preset_name != "Custom" else None
    rows, errors = adapter.load_csv(raw_content, column_mapping=mapping, preset=preset)

    if errors:
        with st.expander(f"Parsing Warnings ({len(errors)})"):
            for err in errors:
                st.warning(err)

    if rows:
        st.subheader("Preview (first 10 rows)")
        preview_df = pd.DataFrame(rows[:10])
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

        st.write(f"**Total rows to import:** {len(rows)}")

        if st.button("Import Data", type="primary"):
            with st.spinner("Importing..."):
                try:
                    # Get or create account
                    if target_acct == 0:
                        acct_id = insert_account(conn, new_acct_name or "CSV Import", "csv_import")
                    else:
                        acct_id = target_acct

                    if import_as == "Trades":
                        trades = adapter.get_trades()
                        for t in trades:
                            t["account_id"] = acct_id
                        count = insert_trades(conn, trades)
                        st.success(f"Imported {count} trades.")
                    else:
                        positions = adapter.get_positions()
                        count = upsert_positions(conn, acct_id, positions)
                        st.success(f"Imported {count} positions.")

                    # Compute and store snapshot
                    all_pos = get_positions(conn, account_id=acct_id)
                    total_val = sum(p["market_value"] or 0 for p in all_pos)
                    upsert_snapshot(conn, acct_id, date.today().isoformat(), total_val)
                    # Aggregate snapshot
                    all_pos_all = get_positions(conn)
                    agg_val = sum(p["market_value"] or 0 for p in all_pos_all)
                    upsert_snapshot(conn, None, date.today().isoformat(), agg_val)

                except Exception as e:
                    st.error(f"Import failed: {e}")
                    logger.error("CSV import error: %s", e)
    else:
        st.warning("No valid rows parsed from the CSV file.")

st.divider()

# ===================================================================
# Manual Trade Entry
# ===================================================================
st.header("Manual Trade Entry")

accounts = get_accounts(conn)
if not accounts:
    st.info("Create an account first via CSV import or brokerage sync.")
else:
    with st.form("manual_trade_form"):
        form_col1, form_col2, form_col3 = st.columns(3)

        with form_col1:
            manual_acct = st.selectbox(
                "Account",
                options=[a["id"] for a in accounts],
                format_func=lambda x: next(
                    (a["name"] for a in accounts if a["id"] == x), str(x)
                ),
                key="manual_acct",
            )
            manual_ticker = st.text_input("Ticker", key="manual_ticker").upper().strip()
            manual_side = st.selectbox("Side", ["buy", "sell"], key="manual_side")

        with form_col2:
            manual_qty = st.number_input("Quantity", min_value=0.0, step=0.01, key="manual_qty")
            manual_price = st.number_input("Price", min_value=0.0, step=0.01, key="manual_price")
            manual_fees = st.number_input("Fees", min_value=0.0, value=0.0, step=0.01, key="manual_fees")

        with form_col3:
            manual_date = st.date_input("Trade Date", value=date.today(), key="manual_date")
            manual_notes = st.text_area("Notes (thesis/reasoning)", key="manual_notes")

        submitted = st.form_submit_button("Add Trade", type="primary")

        if submitted:
            if not manual_ticker:
                st.error("Ticker is required.")
            elif manual_qty <= 0:
                st.error("Quantity must be greater than 0.")
            elif manual_price <= 0:
                st.error("Price must be greater than 0.")
            else:
                trade = {
                    "account_id": manual_acct,
                    "ticker": manual_ticker,
                    "side": manual_side,
                    "quantity": manual_qty,
                    "price": manual_price,
                    "fees": manual_fees,
                    "trade_date": manual_date.isoformat(),
                    "notes": manual_notes,
                    "source": "manual",
                }
                count = insert_trades(conn, [trade])
                st.success(f"Added {manual_side} trade: {manual_qty} {manual_ticker} @ ${manual_price:.2f}")
