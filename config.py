import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Binance API
    API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
    USE_TESTNET: bool = os.getenv("USE_TESTNET", "true").lower() == "true"

    # Trading pair and timeframe
    SYMBOL: str = os.getenv("SYMBOL", "BTC/USDT")
    TIMEFRAME: str = os.getenv("TIMEFRAME", "1h")
    TRADE_AMOUNT_USDT: float = float(os.getenv("TRADE_AMOUNT_USDT", "100"))

    # EMA periods
    EMA_SHORT: int = int(os.getenv("EMA_SHORT", "9"))
    EMA_LONG: int = int(os.getenv("EMA_LONG", "21"))

    # Risk management
    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "2.0"))
    TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "4.0"))

    # Polling interval in seconds
    POLL_INTERVAL: int = 60

    def validate(self) -> None:
        if not self.API_KEY or not self.SECRET_KEY:
            raise ValueError(
                "BINANCE_API_KEY and BINANCE_SECRET_KEY must be set in .env"
            )
        if self.EMA_SHORT >= self.EMA_LONG:
            raise ValueError("EMA_SHORT must be less than EMA_LONG")
