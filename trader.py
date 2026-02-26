import logging
from typing import Optional
import ccxt
import pandas as pd

from config import Config
from strategy import EMAStrategy, Signal
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)

# Gate.io does not support set_sandbox_mode(); testnet is noted in logs only.
_TESTNET_UNSUPPORTED = {"gateio"}


class Trader:
    """Handles exchange interactions and order execution (Binance / Gate.io)."""

    def __init__(self, config: Config):
        self.config = config
        self.strategy = EMAStrategy(
            short_period=config.EMA_SHORT,
            long_period=config.EMA_LONG,
        )
        self.exchange = self._init_exchange()
        self.position: Optional[dict] = None  # current open position
        self.notifier = TelegramNotifier(
            config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID
        )

    def _init_exchange(self) -> ccxt.Exchange:
        exchange_cls = getattr(ccxt, self.config.EXCHANGE)
        exchange: ccxt.Exchange = exchange_cls(
            {
                "apiKey": self.config.API_KEY,
                "secret": self.config.SECRET_KEY,
                "enableRateLimit": True,
            }
        )
        if self.config.USE_TESTNET:
            if self.config.EXCHANGE in _TESTNET_UNSUPPORTED:
                logger.warning(
                    "%s does not support testnet — running against LIVE API. "
                    "Use a sub-account with limited funds for testing.",
                    self.config.EXCHANGE,
                )
            else:
                exchange.set_sandbox_mode(True)
                logger.info("Running in TESTNET mode")
        else:
            logger.warning("Running in LIVE trading mode on %s", self.config.EXCHANGE)
        return exchange

    def fetch_ohlcv(self) -> pd.DataFrame:
        """Fetch recent OHLCV candles from the exchange."""
        limit = self.config.EMA_LONG + 10  # a few extra candles for warm-up
        raw = self.exchange.fetch_ohlcv(
            self.config.SYMBOL, self.config.TIMEFRAME, limit=limit
        )
        df = pd.DataFrame(
            raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def get_balance(self, currency: str = "USDT") -> float:
        balance = self.exchange.fetch_balance()
        return float(balance["free"].get(currency, 0))

    def open_long(self, price: float) -> Optional[dict]:
        """Place a market buy order."""
        usdt_balance = self.get_balance("USDT")
        amount_usdt = min(self.config.TRADE_AMOUNT_USDT, usdt_balance)
        if amount_usdt <= 0:
            logger.warning("Insufficient USDT balance to open position")
            return None

        amount_coin = amount_usdt / price
        order = self.exchange.create_market_buy_order(
            self.config.SYMBOL, amount_coin
        )
        logger.info(
            "BUY  %s | qty=%.6f | price=%.2f | cost=%.2f USDT",
            self.config.SYMBOL, amount_coin, price, amount_usdt,
        )
        sl = price * (1 - self.config.STOP_LOSS_PCT / 100)
        tp = price * (1 + self.config.TAKE_PROFIT_PCT / 100)
        self.position = {
            "side": "long",
            "entry_price": price,
            "amount": amount_coin,
            "stop_loss": sl,
            "take_profit": tp,
        }
        self.notifier.on_buy(self.config.SYMBOL, price, amount_coin, sl, tp)
        return order

    def close_long(self, price: float, reason: str = "signal") -> Optional[dict]:
        """Place a market sell order to close current long position."""
        if not self.position:
            return None

        amount = self.position["amount"]
        order = self.exchange.create_market_sell_order(self.config.SYMBOL, amount)
        pnl_pct = (price - self.position["entry_price"]) / self.position["entry_price"] * 100
        logger.info(
            "SELL %s | qty=%.6f | price=%.2f | PnL=%.2f%% | reason=%s",
            self.config.SYMBOL, amount, price, pnl_pct, reason,
        )
        self.notifier.on_sell(self.config.SYMBOL, price, pnl_pct, reason)
        self.position = None
        return order

    def check_risk_management(self, current_price: float) -> bool:
        """
        Check stop-loss and take-profit levels.
        Returns True if position was closed.
        """
        if not self.position:
            return False

        if current_price <= self.position["stop_loss"]:
            logger.warning("Stop-loss triggered at %.2f", current_price)
            self.close_long(current_price, reason="stop_loss")
            return True

        if current_price >= self.position["take_profit"]:
            logger.info("Take-profit triggered at %.2f", current_price)
            self.close_long(current_price, reason="take_profit")
            return True

        return False

    def run_once(self) -> None:
        """Execute one trading cycle: fetch data → analyze → act."""
        df = self.fetch_ohlcv()
        current_price = float(df["close"].iloc[-1])

        # Risk management check first
        if self.check_risk_management(current_price):
            return

        signal, info = self.strategy.analyze(df)
        logger.info(
            "Signal: %s | close=%.4f | EMA%d=%.4f | EMA%d=%.4f | %s",
            signal.value,
            info.get("close", 0),
            self.config.EMA_SHORT, info.get("ema_short", 0),
            self.config.EMA_LONG, info.get("ema_long", 0),
            info.get("reason", ""),
        )

        if signal == Signal.BUY and not self.position:
            self.open_long(current_price)
        elif signal == Signal.SELL and self.position:
            self.close_long(current_price, reason="signal")
