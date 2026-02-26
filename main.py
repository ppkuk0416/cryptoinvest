"""
Crypto Auto Trading Bot — Binance EMA Golden/Dead Cross Strategy
Usage:
    1. Copy .env.example to .env and fill in your API keys
    2. pip install -r requirements.txt
    3. python main.py
"""

import logging
import time
import signal
import sys

from config import Config
from trader import Trader
from notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log"),
    ],
)
logger = logging.getLogger(__name__)

_running = True


def _handle_signal(sig, frame):
    global _running
    logger.info("Shutdown signal received. Stopping bot...")
    _running = False


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    config = Config()
    try:
        config.validate()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("Crypto Trading Bot started")
    logger.info("Exchange : %s", config.EXCHANGE)
    logger.info("Symbol   : %s", config.SYMBOL)
    logger.info("Timeframe: %s", config.TIMEFRAME)
    logger.info("EMA      : %d / %d", config.EMA_SHORT, config.EMA_LONG)
    logger.info("SL/TP    : %.1f%% / %.1f%%", config.STOP_LOSS_PCT, config.TAKE_PROFIT_PCT)
    logger.info("Testnet  : %s", config.USE_TESTNET)
    logger.info("=" * 50)

    trader = Trader(config)
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)

    while _running:
        try:
            trader.run_once()
        except Exception as e:
            logger.error("Error during trading cycle: %s", e, exc_info=True)
            notifier.on_error(str(e))

        if _running:
            logger.debug("Sleeping %d seconds...", config.POLL_INTERVAL)
            time.sleep(config.POLL_INTERVAL)

    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
