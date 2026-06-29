"""engine.py — a minimal, look-ahead-safe backtest engine.

Core discipline (from fx-project-rules):
  - No look-ahead: the signal at bar i uses only bars[0..i]; the order executes
    at bar i+1's open. We never use a bar's own close/high/low to decide a trade
    placed within that same bar.
  - Stop-loss is mandatory: every position carries a stop, sized so the loss
    equals the intended risk (see sizing.py).
  - Costs are always applied: gross PnL is passed through CostModel.net_pnl.

This is a SKELETON for learning and iteration — long-only, one position at a
time, single instrument. Extend deliberately; keep parameters few to avoid
overfitting.
"""

from dataclasses import dataclass, field
import pandas as pd

from sizing import compute_position
from costs import CostModel


@dataclass
class BacktestConfig:
    account: float = 300_000.0
    risk_pct: float = 1.0
    stop_pips: float = 50.0
    pip_size: float = 0.01            # 0.01 for JPY pairs
    quote_to_account_rate: float = 1.0
    costs: CostModel = field(default_factory=CostModel)


def _nights(entry_time, exit_time):
    return max(0, (pd.Timestamp(exit_time).normalize() - pd.Timestamp(entry_time).normalize()).days)


def run_backtest(df, strategy, config: BacktestConfig):
    """Run a long-only backtest. `df` must be cleaned, time-sorted OHLC with a
    'timestamp' column. Returns (trades_df, summary)."""
    df = df.reset_index(drop=True)
    trades = []

    position = 0
    entry_price = entry_time = stop_price = units = None

    last_tradable = len(df) - 1  # we act on i+1, so loop i to len-2
    for i in range(strategy.warmup, last_tradable):
        hist = df.iloc[: i + 1]            # bars up to and including the closed bar i
        sig = strategy.signal(hist, position)  # decision uses only closed-bar info
        nxt = df.iloc[i + 1]               # the bar we can actually trade on
        exec_open = nxt["open"]

        if position == 1:
            # 1) stop-loss check against the next bar's low (intrabar)
            if nxt["low"] <= stop_price:
                exit_price = stop_price    # filled at stop; slippage handled in costs
                _close(trades, entry_time, entry_price, nxt["timestamp"], exit_price,
                       units, config, reason="stop")
                position = 0
                continue
            # 2) signal flip -> exit at next open
            if sig == 0:
                _close(trades, entry_time, entry_price, nxt["timestamp"], exec_open,
                       units, config, reason="signal")
                position = 0
                continue

        elif position == 0 and sig == 1:
            # enter long at next bar's open
            entry_price = exec_open
            entry_time = nxt["timestamp"]
            stop_price = entry_price - config.stop_pips * config.pip_size
            pos = compute_position(
                config.account, config.risk_pct, config.stop_pips, entry_price,
                config.pip_size, config.quote_to_account_rate,
            )
            units = pos["units"]
            if pos["exceeds_cap"]:
                # respect the leverage cap; skip this entry rather than break the rule
                position = 0
                entry_price = None
                continue
            position = 1

    # close any open position at the final bar's close (mark-to-market exit)
    if position == 1:
        last = df.iloc[-1]
        _close(trades, entry_time, entry_price, last["timestamp"], last["close"],
               units, config, reason="end")

    trades_df = pd.DataFrame(trades)
    summary = {
        "trades": len(trades_df),
        "total_net_pnl": float(trades_df["net_pnl"].sum()) if len(trades_df) else 0.0,
    }
    return trades_df, summary


def _close(trades, entry_time, entry_price, exit_time, exit_price, units, config, reason):
    gross = (exit_price - entry_price) * units
    net = config.costs.net_pnl(gross, units, _nights(entry_time, exit_time))
    trades.append({
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "units": units,
        "gross_pnl": gross,
        "net_pnl": net,
        "reason": reason,
    })
