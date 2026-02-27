"""InvestView — Streamlit entry point."""

import sys
from pathlib import Path

# Ensure investview package is importable when running from project root
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from db.database import get_connection, init_db
from config import logger

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="InvestView",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialize session state
# ---------------------------------------------------------------------------
if "db_conn" not in st.session_state:
    conn = get_connection()
    init_db(conn)
    st.session_state.db_conn = conn
    logger.info("Database connection established and schema initialized.")

if "ibkr_adapter" not in st.session_state:
    st.session_state.ibkr_adapter = None

if "etrade_adapter" not in st.session_state:
    st.session_state.etrade_adapter = None

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("InvestView")
st.sidebar.caption("Investment Portfolio Tracker")

# Define pages
dashboard_page = st.Page("pages/01_dashboard.py", title="Dashboard", icon="📊", default=True)
positions_page = st.Page("pages/02_positions.py", title="Positions", icon="📋")
charts_page = st.Page("pages/03_charts.py", title="Charts", icon="📈")
import_page = st.Page("pages/04_import.py", title="Import & Sync", icon="🔄")

pg = st.navigation([dashboard_page, positions_page, charts_page, import_page])
pg.run()
