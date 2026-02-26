"""
Telegram notification module.
Sends trading events to a Telegram chat via Bot API.
Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env to enable.
If not configured, all calls are silently skipped.
"""

import logging
import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self._enabled = bool(token and chat_id)
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id

    def _send(self, text: str) -> None:
        if not self._enabled:
            return
        try:
            resp = requests.post(
                self._url,
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            if not resp.ok:
                logger.warning("Telegram API error %d: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Telegram notification failed: %s", e)

    def on_buy(self, symbol: str, price: float, amount: float, sl: float, tp: float) -> None:
        self._send(
            f"🟢 <b>BUY</b> {symbol}\n"
            f"Price : <code>{price:.4f}</code>\n"
            f"Amount: <code>{amount:.6f}</code>\n"
            f"SL    : <code>{sl:.4f}</code>\n"
            f"TP    : <code>{tp:.4f}</code>"
        )

    def on_sell(self, symbol: str, price: float, pnl_pct: float, reason: str) -> None:
        icon = "🔴" if pnl_pct < 0 else "🟡"
        self._send(
            f"{icon} <b>SELL</b> {symbol}\n"
            f"Price : <code>{price:.4f}</code>\n"
            f"PnL   : <code>{pnl_pct:+.2f}%</code>\n"
            f"Reason: {reason}"
        )

    def on_error(self, message: str) -> None:
        self._send(f"⚠️ <b>Bot Error</b>\n<code>{message}</code>")
