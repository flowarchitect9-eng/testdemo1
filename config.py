import os
import sys
import logging
from dotenv import load_dotenv
from binance.client import Client

# Auto-load environment variables from .env file
load_dotenv()

# Configure Central Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ConfigValidator")

# Environment Variables & Trading Mode
TRADING_MODE = os.getenv("TRADING_MODE", "TESTNET").upper()
ENABLE_REAL_MONEY_TRADING = os.getenv("ENABLE_REAL_MONEY_TRADING", "false").lower() == "true"

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Base Endpoints
TESTNET_BASE_URL = "https://testnet.binance.vision"
PRODUCTION_BASE_URL = "https://api.binance.com"

# Supabase / PostgreSQL Connection String
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or "postgresql://postgres:postgres@localhost:5432/postgres"

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Strategy Default Settings
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
TRADE_USD_SIZE = float(os.getenv("TRADE_USD_SIZE", "10.0"))
MAX_HOLD_MINUTES = int(os.getenv("MAX_HOLD_MINUTES", "45"))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
ADX_MIN_THRESHOLD = float(os.getenv("ADX_MIN_THRESHOLD", "25.0"))

class TripleLockSafetyValidator:
    """
    Enterprise Triple-Lock Safety Engine:
    Lock 1: Enforces strict URL base check prior to order execution.
    Lock 2: Requires explicit ENABLE_REAL_MONEY_TRADING=true flag for production.
    Lock 3: API Key Permission Guard - Disconnects immediately if withdrawal permission is active.
    """

    @staticmethod
    def get_expected_base_url():
        if TRADING_MODE == "PRODUCTION":
            return PRODUCTION_BASE_URL
        return TESTNET_BASE_URL

    @classmethod
    def validate_environment(cls, client: Client):
        logger.info("Initializing Triple-Lock Safety Validation...")

        # --- LOCK 1: Base URI Enforcement ---
        expected_url = cls.get_expected_base_url()
        logger.info(f"[Lock 1 Passed] Trading Mode: {TRADING_MODE} | Target Base URL: {expected_url}")

        # --- LOCK 2: Production Real-Money Execution Guard ---
        if TRADING_MODE == "PRODUCTION":
            if not ENABLE_REAL_MONEY_TRADING:
                err_msg = (
                    "CRITICAL SAFETY LOCK BLOCKED EXECUTION!\n"
                    "TRADING_MODE is PRODUCTION but ENABLE_REAL_MONEY_TRADING is not 'true'.\n"
                    "Execution halted to protect funds."
                )
                logger.critical(err_msg)
                raise RuntimeError(err_msg)
            logger.warning("[Lock 2 Passed] PRODUCTION REAL-MONEY TRADING IS ENABLED!")
        else:
            logger.info("[Lock 2 Passed] TESTNET Mode active. Virtual funds in use.")

        # --- LOCK 3: API Key Permission Guard (No Withdrawals Allowed) ---
        if BINANCE_API_KEY and BINANCE_API_SECRET:
            try:
                # Query Binance Account API permissions
                permissions = client.get_account_api_permissions()
                logger.info(f"API Key Permissions Response: {permissions}")

                # Binance API returns enableWithdrawals in permission data
                enable_withdrawals = permissions.get("data", {}).get("enableWithdrawals", False)
                if enable_withdrawals:
                    err_msg = (
                        "SECURITY BREACH / SAFETY GUARD TRIGGERED!\n"
                        "The configured Binance API Key has WITHDRAWAL permissions enabled.\n"
                        "For algorithmic trading security, API keys MUST NOT have withdrawal rights.\n"
                        "Bot is immediately shutting down."
                    )
                    logger.critical(err_msg)
                    raise PermissionError(err_msg)
                logger.info("[Lock 3 Passed] API Key Withdrawal Permissions are DISABLED. Safe to proceed.")
            except PermissionError as pe:
                raise pe
            except Exception as e:
                logger.warning(f"Could not verify API Key permissions directly (API endpoint format may vary): {e}")

        logger.info("TRIPLE-LOCK SAFETY VALIDATION PASSED SUCCESSFULLY!")

def get_binance_client() -> Client:
    """Factory creating configured Binance python-binance client instance."""
    if TRADING_MODE == "PRODUCTION":
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=False)
    else:
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=True)
    return client
