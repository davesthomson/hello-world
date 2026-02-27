"""Application configuration loaded from environment variables."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the investview directory
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# IBKR
# ---------------------------------------------------------------------------
IBKR_HOST: str = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT: int = int(os.getenv("IBKR_PORT", "7497"))
IBKR_CLIENT_ID: int = int(os.getenv("IBKR_CLIENT_ID", "1"))

# ---------------------------------------------------------------------------
# E*Trade
# ---------------------------------------------------------------------------
ETRADE_CONSUMER_KEY: str = os.getenv("ETRADE_CONSUMER_KEY", "")
ETRADE_CONSUMER_SECRET: str = os.getenv("ETRADE_CONSUMER_SECRET", "")
ETRADE_SANDBOX: bool = os.getenv("ETRADE_SANDBOX", "true").lower() == "true"
ETRADE_BASE_URL: str = (
    "https://apisb.etrade.com"
    if ETRADE_SANDBOX
    else "https://api.etrade.com"
)

# ---------------------------------------------------------------------------
# FRED
# ---------------------------------------------------------------------------
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# App / Database
# ---------------------------------------------------------------------------
DB_PATH: str = os.getenv("DB_PATH", str(Path(__file__).parent / "investview.db"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("investview")
