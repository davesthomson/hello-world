"""Application configuration loaded from .env file."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# --- Interactive Brokers ---
IBKR_HOST: str = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT: int = int(os.getenv("IBKR_PORT", "7497"))
IBKR_CLIENT_ID: int = int(os.getenv("IBKR_CLIENT_ID", "1"))

# --- FRED ---
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# --- App Settings ---
DB_PATH: str = os.getenv("DB_PATH", "data/investview.db")
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
PORT: int = int(os.getenv("PORT", "8050"))
