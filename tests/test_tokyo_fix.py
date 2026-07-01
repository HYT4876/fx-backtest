"""test_tokyo_fix.py — regression check for TokyoFixDriftStrategy's timing.

Confirms the strategy enters at the 09:00 JST bar's open (the bar closing at
08:00 signals it) and exits exactly one bar later at the 10:00 JST open,
once per day, on synthetic hourly JST-timestamped data.

Run: python3 tests/test_tokyo_fix.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from engine import run_backtest, BacktestConfig
from strategy import TokyoFixDriftStrategy


def _hourly_df(days=2, price=150.0):
    times = pd.date_range("2024-01-01 00:00", periods=24 * days, freq="h")
    return pd.DataFrame({"timestamp": times, "open": price, "high": price,
                          "low": price, "close": price})


def test_enters_at_09_exits_at_10_once_per_day():
    df = _hourly_df(days=2)
    config = BacktestConfig()
    trades, summary = run_backtest(df, TokyoFixDriftStrategy(entry_hour_jst=8), config)

    assert summary["trades"] == 2
    for _, row in trades.iterrows():
        assert pd.Timestamp(row["entry_time"]).hour == 9
        assert pd.Timestamp(row["exit_time"]).hour == 10
        assert row["reason"] == "signal"
    # one trade on each of the two synthetic days
    assert trades.iloc[0]["entry_time"].date() != trades.iloc[1]["entry_time"].date()


def test_entry_hour_is_configurable():
    df = _hourly_df(days=1)
    config = BacktestConfig()
    trades, summary = run_backtest(df, TokyoFixDriftStrategy(entry_hour_jst=14), config)

    assert summary["trades"] == 1
    assert pd.Timestamp(trades.iloc[0]["entry_time"]).hour == 15


if __name__ == "__main__":
    test_enters_at_09_exits_at_10_once_per_day()
    test_entry_hour_is_configurable()
    print("OK: all tokyo-fix strategy tests passed")
