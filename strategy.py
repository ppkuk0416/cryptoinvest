"""
Trading strategy: EMA Golden Cross + ADX regime filter + RSI confirmation + Volume spike.

Entry (BUY):
  1. EMA(short) crosses above EMA(long)              — trend direction
  2. ADX(14) > threshold (default 20)                — not a ranging/choppy market
  3. RSI(14) between RSI_MIN and RSI_MAX (45–65)     — momentum confirming, not overbought
  4. Current volume > VOLUME_SPIKE_MULT × 20-bar MA  — institutional participation

Exit (SELL):
  - EMA dead cross (short crosses below long)
  - OR RSI >= 70 (overbought — exit before reversal)
"""

from enum import Enum
from typing import Optional
import pandas as pd

try:
    import pandas_ta as ta
    _HAS_PANDAS_TA = True
except ImportError:
    _HAS_PANDAS_TA = False


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    if _HAS_PANDAS_TA:
        return ta.rsi(series, length=period)
    # Fallback: Wilder's smoothed RSI
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average Directional Index — measures trend strength (not direction)."""
    if _HAS_PANDAS_TA:
        result = ta.adx(high, low, close, length=period)
        col = f"ADX_{period}"
        return result[col] if col in result.columns else result.iloc[:, 0]
    # Fallback: manual ADX
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    up_move = high - high.shift()
    down_move = low.shift() - low
    pos_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    neg_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    smooth_pos = pos_dm.ewm(alpha=1 / period, adjust=False).mean()
    smooth_neg = neg_dm.ewm(alpha=1 / period, adjust=False).mean()
    dip = 100 * smooth_pos / atr.replace(0, float("nan"))
    dim = 100 * smooth_neg / atr.replace(0, float("nan"))
    dx = (100 * (dip - dim).abs() / (dip + dim).replace(0, float("nan")))
    return dx.ewm(alpha=1 / period, adjust=False).mean()


class EMAStrategy:
    """
    Stage-1 enhanced strategy: EMA crossover gated by ADX + RSI + Volume.

    Parameters
    ----------
    short_period      : EMA fast period (default 9)
    long_period       : EMA slow period (default 21)
    adx_period        : ADX smoothing period (default 14)
    adx_threshold     : Min ADX to trade — below this = ranging, skip all signals (default 20)
    rsi_period        : RSI period (default 14)
    rsi_min / rsi_max : RSI window for BUY entry (default 45–65)
    volume_ma_period  : Rolling window for average volume (default 20)
    volume_spike_mult : Volume must exceed avg × this multiplier (default 1.3)
    """

    def __init__(
        self,
        short_period: int = 9,
        long_period: int = 21,
        adx_period: int = 14,
        adx_threshold: float = 20.0,
        rsi_period: int = 14,
        rsi_min: float = 45.0,
        rsi_max: float = 65.0,
        volume_ma_period: int = 20,
        volume_spike_mult: float = 1.3,
    ):
        self.short_period = short_period
        self.long_period = long_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.rsi_period = rsi_period
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.volume_ma_period = volume_ma_period
        self.volume_spike_mult = volume_spike_mult

    # ------------------------------------------------------------------
    # Minimum candles needed before the strategy can produce a signal
    # ------------------------------------------------------------------
    @property
    def warmup_bars(self) -> int:
        return max(self.long_period, self.adx_period, self.rsi_period, self.volume_ma_period) + 5

    # ------------------------------------------------------------------

    def analyze(self, df: pd.DataFrame) -> tuple[Signal, dict]:
        """
        Analyze OHLCV dataframe and return a trading signal.

        Args:
            df: DataFrame with columns open/high/low/close/volume,
                indexed by timestamp (newest last).

        Returns:
            (Signal, info_dict)
        """
        if len(df) < self.warmup_bars:
            return Signal.HOLD, {"reason": "Not enough candles for warmup"}

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ── Indicators ────────────────────────────────────────────────
        ema_short = _ema(close, self.short_period)
        ema_long = _ema(close, self.long_period)
        rsi = _rsi(close, self.rsi_period)
        adx = _adx(high, low, close, self.adx_period)
        vol_ma = close.rolling(self.volume_ma_period).mean()  # reuse close window for smoothing
        vol_ma_v = volume.rolling(self.volume_ma_period).mean()

        # Latest values
        curr_short = ema_short.iloc[-1]
        curr_long = ema_long.iloc[-1]
        prev_short = ema_short.iloc[-2]
        prev_long = ema_long.iloc[-2]
        curr_rsi = rsi.iloc[-1]
        curr_adx = adx.iloc[-1]
        curr_vol = volume.iloc[-1]
        curr_vol_ma = vol_ma_v.iloc[-1]

        info = {
            "ema_short": round(curr_short, 4),
            "ema_long": round(curr_long, 4),
            "rsi": round(curr_rsi, 2) if pd.notna(curr_rsi) else None,
            "adx": round(curr_adx, 2) if pd.notna(curr_adx) else None,
            "vol_ratio": round(curr_vol / curr_vol_ma, 2) if curr_vol_ma else None,
            "close": round(close.iloc[-1], 4),
        }

        # ── SELL: dead cross OR RSI overbought ─────────────────────────
        dead_cross = prev_short >= prev_long and curr_short < curr_long
        rsi_overbought = pd.notna(curr_rsi) and curr_rsi >= 70

        if dead_cross:
            info["reason"] = "Dead Cross (EMA crossover downward)"
            return Signal.SELL, info
        if rsi_overbought:
            info["reason"] = f"RSI overbought ({curr_rsi:.1f} >= 70) — exit before reversal"
            return Signal.SELL, info

        # ── BUY: golden cross + all 3 filters ─────────────────────────
        golden_cross = prev_short <= prev_long and curr_short > curr_long

        if not golden_cross:
            info["reason"] = "No crossover detected"
            return Signal.HOLD, info

        # Filter 1 — ADX: skip if market is ranging
        if pd.notna(curr_adx) and curr_adx < self.adx_threshold:
            info["reason"] = (
                f"Golden Cross blocked: ADX {curr_adx:.1f} < {self.adx_threshold} "
                f"(ranging market — high false-signal risk)"
            )
            return Signal.HOLD, info

        # Filter 2 — RSI: confirm momentum without being overbought
        if pd.notna(curr_rsi) and not (self.rsi_min <= curr_rsi <= self.rsi_max):
            info["reason"] = (
                f"Golden Cross blocked: RSI {curr_rsi:.1f} outside [{self.rsi_min}, {self.rsi_max}] "
                f"({'overbought' if curr_rsi > self.rsi_max else 'no momentum yet'})"
            )
            return Signal.HOLD, info

        # Filter 3 — Volume: confirm with institutional participation
        if curr_vol_ma and curr_vol < curr_vol_ma * self.volume_spike_mult:
            info["reason"] = (
                f"Golden Cross blocked: volume ratio {curr_vol / curr_vol_ma:.2f}x "
                f"< {self.volume_spike_mult}x (low-conviction move)"
            )
            return Signal.HOLD, info

        info["reason"] = (
            f"Golden Cross confirmed — ADX {curr_adx:.1f}, "
            f"RSI {curr_rsi:.1f}, vol {curr_vol / curr_vol_ma:.2f}x avg"
        )
        return Signal.BUY, info
