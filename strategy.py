from enum import Enum
from typing import Optional
import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


class EMAStrategy:
    """
    Golden Cross / Dead Cross strategy using two EMAs.

    - Golden Cross: short EMA crosses above long EMA → BUY signal
    - Dead Cross:   short EMA crosses below long EMA → SELL signal
    """

    def __init__(self, short_period: int = 9, long_period: int = 21):
        self.short_period = short_period
        self.long_period = long_period

    def analyze(self, df: pd.DataFrame) -> tuple[Signal, dict]:
        """
        Analyze OHLCV dataframe and return a trading signal.

        Args:
            df: DataFrame with at minimum a 'close' column,
                indexed by timestamp (newest last).

        Returns:
            (Signal, info_dict) where info_dict contains EMA values.
        """
        if len(df) < self.long_period + 1:
            return Signal.HOLD, {"reason": "Not enough candles"}

        close = df["close"]
        ema_short = calculate_ema(close, self.short_period)
        ema_long = calculate_ema(close, self.long_period)

        prev_short = ema_short.iloc[-2]
        prev_long = ema_long.iloc[-2]
        curr_short = ema_short.iloc[-1]
        curr_long = ema_long.iloc[-1]

        info = {
            "ema_short": round(curr_short, 4),
            "ema_long": round(curr_long, 4),
            "prev_ema_short": round(prev_short, 4),
            "prev_ema_long": round(prev_long, 4),
            "close": round(close.iloc[-1], 4),
        }

        # Golden Cross: short crossed above long
        if prev_short <= prev_long and curr_short > curr_long:
            info["reason"] = "Golden Cross (EMA crossover upward)"
            return Signal.BUY, info

        # Dead Cross: short crossed below long
        if prev_short >= prev_long and curr_short < curr_long:
            info["reason"] = "Dead Cross (EMA crossover downward)"
            return Signal.SELL, info

        info["reason"] = "No crossover detected"
        return Signal.HOLD, info
