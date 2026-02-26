import os
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_EXCHANGES = ("binance", "gateio", "upbit")


class Config:
    # Exchange selection: "binance", "gateio", or "upbit"
    EXCHANGE: str = os.getenv("EXCHANGE", "binance").lower()

    # Binance API
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")

    # Gate.io API
    GATEIO_API_KEY: str = os.getenv("GATEIO_API_KEY", "")
    GATEIO_SECRET_KEY: str = os.getenv("GATEIO_SECRET_KEY", "")

    # Upbit API (no testnet support — always live)
    # Get your keys from: https://upbit.com/mypage/open_api_management
    UPBIT_API_KEY: str = os.getenv("UPBIT_API_KEY", "")
    UPBIT_SECRET_KEY: str = os.getenv("UPBIT_SECRET_KEY", "")

    USE_TESTNET: bool = os.getenv("USE_TESTNET", "true").lower() == "true"

    # Trading pair and timeframe
    SYMBOL: str = os.getenv("SYMBOL", "BTC/USDT")
    TIMEFRAME: str = os.getenv("TIMEFRAME", "1h")
    TRADE_AMOUNT: float = float(os.getenv("TRADE_AMOUNT", "100"))

    # EMA periods
    EMA_SHORT: int = int(os.getenv("EMA_SHORT", "9"))
    EMA_LONG: int = int(os.getenv("EMA_LONG", "21"))

    # Risk management
    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "2.0"))
    TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "4.0"))

    # Polling interval in seconds
    POLL_INTERVAL: int = 60

    # Telegram notifications (optional — leave blank to disable)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def TRADE_CURRENCY(self) -> str:
        """Base currency used for balance and order sizing."""
        return "KRW" if self.EXCHANGE == "upbit" else "USDT"

    @property
    def API_KEY(self) -> str:
        if self.EXCHANGE == "binance":
            return self.BINANCE_API_KEY
        if self.EXCHANGE == "gateio":
            return self.GATEIO_API_KEY
        return self.UPBIT_API_KEY

    @property
    def SECRET_KEY(self) -> str:
        if self.EXCHANGE == "binance":
            return self.BINANCE_SECRET_KEY
        if self.EXCHANGE == "gateio":
            return self.GATEIO_SECRET_KEY
        return self.UPBIT_SECRET_KEY

    def validate(self) -> None:
        if self.EXCHANGE not in SUPPORTED_EXCHANGES:
            raise ValueError(
                f"EXCHANGE must be one of {SUPPORTED_EXCHANGES}, got '{self.EXCHANGE}'"
            )
        if not self.API_KEY or not self.SECRET_KEY:
            raise ValueError(
                f"{self.EXCHANGE.upper()} API key and secret must be set in .env"
            )
        if self.EMA_SHORT >= self.EMA_LONG:
            raise ValueError("EMA_SHORT must be less than EMA_LONG")
