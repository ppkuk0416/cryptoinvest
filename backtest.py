"""
Backtesting script — EMA Golden/Dead Cross strategy.

Usage:
    python backtest.py                     # uses settings from .env
    python backtest.py --limit 1000        # more candles
    python backtest.py --symbol ETH/USDT --timeframe 4h
"""

import argparse
import sys
import ccxt
import pandas as pd

from config import Config
from strategy import EMAStrategy, Signal


def fetch_ohlcv(config: Config, limit: int) -> pd.DataFrame:
    exchange_cls = getattr(ccxt, config.EXCHANGE)
    exchange = exchange_cls({"enableRateLimit": True})
    raw = exchange.fetch_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=limit)
    df = pd.DataFrame(
        raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def run_backtest(config: Config, limit: int = 500) -> None:
    print(f"Fetching {limit} candles for {config.SYMBOL} {config.TIMEFRAME} from {config.EXCHANGE}...")
    df = fetch_ohlcv(config, limit)

    strategy = EMAStrategy(config.EMA_SHORT, config.EMA_LONG)
    trades = []
    position = None
    equity = 100.0  # start with 100 base units for cumulative P&L

    warmup = config.EMA_LONG + 1
    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        signal, _ = strategy.analyze(window)
        price = float(df["close"].iloc[i])
        ts = df.index[i]

        # Apply stop-loss / take-profit if in position
        if position:
            if price <= position["sl"]:
                pnl_pct = (price - position["entry"]) / position["entry"] * 100
                equity *= 1 + pnl_pct / 100
                trades.append(_make_trade(position, price, ts, pnl_pct, "stop_loss"))
                position = None
                continue
            if price >= position["tp"]:
                pnl_pct = (price - position["entry"]) / position["entry"] * 100
                equity *= 1 + pnl_pct / 100
                trades.append(_make_trade(position, price, ts, pnl_pct, "take_profit"))
                position = None
                continue

        if signal == Signal.BUY and position is None:
            position = {
                "entry": price,
                "entry_time": ts,
                "sl": price * (1 - config.STOP_LOSS_PCT / 100),
                "tp": price * (1 + config.TAKE_PROFIT_PCT / 100),
            }
        elif signal == Signal.SELL and position is not None:
            pnl_pct = (price - position["entry"]) / position["entry"] * 100
            equity *= 1 + pnl_pct / 100
            trades.append(_make_trade(position, price, ts, pnl_pct, "signal"))
            position = None

    if not trades:
        print("No completed trades found in this period.")
        return

    trades_df = pd.DataFrame(trades)
    _print_report(trades_df, config, equity)


def _make_trade(position: dict, exit_price: float, exit_time, pnl_pct: float, exit_reason: str) -> dict:
    return {
        "entry_time": position["entry_time"],
        "exit_time": exit_time,
        "entry_price": round(position["entry"], 4),
        "exit_price": round(exit_price, 4),
        "pnl_pct": round(pnl_pct, 2),
        "exit_reason": exit_reason,
        "result": "WIN" if pnl_pct > 0 else "LOSS",
    }


def _print_report(trades_df: pd.DataFrame, config: Config, final_equity: float) -> None:
    total = len(trades_df)
    wins = (trades_df["result"] == "WIN").sum()
    losses = total - wins
    win_rate = wins / total * 100
    total_pnl = trades_df["pnl_pct"].sum()
    avg_pnl = trades_df["pnl_pct"].mean()
    best = trades_df["pnl_pct"].max()
    worst = trades_df["pnl_pct"].min()

    # Max drawdown: largest peak-to-trough in cumulative P&L
    cumulative = (1 + trades_df["pnl_pct"] / 100).cumprod()
    peak = cumulative.cummax()
    drawdown = ((cumulative - peak) / peak * 100).min()

    print(f"\n{'='*70}")
    print(f"  Backtest Report: {config.SYMBOL} | {config.TIMEFRAME} | "
          f"EMA{config.EMA_SHORT}/{config.EMA_LONG} | SL{config.STOP_LOSS_PCT}%/TP{config.TAKE_PROFIT_PCT}%")
    print(f"{'='*70}")
    print(trades_df[["entry_time", "exit_time", "entry_price", "exit_price", "pnl_pct", "exit_reason", "result"]]
          .to_string(index=False))
    print(f"{'='*70}")
    print(f"  Total trades   : {total}  ({wins}W / {losses}L)")
    print(f"  Win rate       : {win_rate:.1f}%")
    print(f"  Total PnL      : {total_pnl:+.2f}%")
    print(f"  Avg PnL/trade  : {avg_pnl:+.2f}%")
    print(f"  Best trade     : {best:+.2f}%")
    print(f"  Worst trade    : {worst:+.2f}%")
    print(f"  Max drawdown   : {drawdown:.2f}%")
    print(f"  Final equity   : {final_equity:.2f}  (started at 100)")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest EMA crossover strategy")
    parser.add_argument("--symbol", type=str, help="Trading pair (e.g. ETH/USDT)")
    parser.add_argument("--timeframe", type=str, help="Candle timeframe (e.g. 1h, 4h)")
    parser.add_argument("--limit", type=int, default=500, help="Number of candles (default: 500)")
    args = parser.parse_args()

    config = Config()
    if args.symbol:
        config.SYMBOL = args.symbol
    if args.timeframe:
        config.TIMEFRAME = args.timeframe

    try:
        run_backtest(config, limit=args.limit)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
