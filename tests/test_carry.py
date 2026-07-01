"""test_carry.py — regression check for CarryTrendStrategy.

Confirms:
  - the trend filter is long above its moving average and flat below it;
  - positive swap actually improves net PnL for a held long (the carry edge
    flows through the cost model), while raw signal timing is unchanged.

Run: python3 tests/test_carry.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from engine import run_backtest, BacktestConfig
from costs import CostModel
from strategy import CarryTrendStrategy


def _ramp_df(n=60, start=150.0, step=0.05):
    # steadily rising price -> close stays above its trailing SMA -> long
    times = pd.date_range("2024-01-01 00:00", periods=n, freq="h")
    close = start + np.arange(n) * step
    return pd.DataFrame({"timestamp": times, "open": close, "high": close + 0.01,
                         "low": close - 0.01, "close": close})


def test_long_in_uptrend():
    df = _ramp_df()
    trades, summary = run_backtest(df, CarryTrendStrategy(trend_window=20), BacktestConfig())
    # a persistent uptrend should keep us long -> at least one trade opened
    assert summary["trades"] >= 1


def test_flat_when_below_ma():
    # rising then sharply falling: after the drop, close < SMA -> flat/exit
    up = _ramp_df(n=40)
    down_close = up["close"].iloc[-1] - np.arange(1, 21) * 0.3
    times = pd.date_range("2024-01-02 16:00", periods=20, freq="h")
    down = pd.DataFrame({"timestamp": times, "open": down_close, "high": down_close + 0.01,
                         "low": down_close - 0.01, "close": down_close})
    df = pd.concat([up, down], ignore_index=True)
    trades, _ = run_backtest(df, CarryTrendStrategy(trend_window=20), BacktestConfig())
    # the position must be closed by the downtrend, not still open at the end
    assert not trades.empty
    assert trades.iloc[-1]["reason"] in ("signal", "stop")


def test_positive_swap_improves_net():
    df = _ramp_df(n=60)
    no_swap = CostModel(swap_per_10k_per_night=0.0, pip_value_per_unit=0.01)
    with_swap = CostModel(swap_per_10k_per_night=100.0, pip_value_per_unit=0.01)
    t0, _ = run_backtest(df, CarryTrendStrategy(trend_window=20),
                         BacktestConfig(costs=no_swap))
    t1, _ = run_backtest(df, CarryTrendStrategy(trend_window=20),
                         BacktestConfig(costs=with_swap))
    # same trades, but positive carry should lift net PnL (held across nights)
    assert len(t0) == len(t1) and len(t0) >= 1
    assert t1["net_pnl"].sum() > t0["net_pnl"].sum()


if __name__ == "__main__":
    test_long_in_uptrend()
    test_flat_when_below_ma()
    test_positive_swap_improves_net()
    print("OK: all carry strategy tests passed")
