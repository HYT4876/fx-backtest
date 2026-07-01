"""test_news.py — regression check for the news filter and its engine wiring.

Confirms:
  - is_blocked/filter_times classify candidate times correctly (mirrors the
    news-filter skill's own worked example).
  - engine.run_backtest blocks NEW entries during a blocked window but never
    blocks an existing position's stop-loss or signal-flip exit (risk
    management must keep working around news).

Run: python3 tests/test_news.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from news import is_blocked, filter_times
from engine import run_backtest, BacktestConfig


def test_is_blocked_matches_skill_example():
    events = [
        {"time": "2024-02-02 22:30", "impact": "high"},
        {"time": "2024-02-01 12:00", "impact": "medium"},
    ]
    blocked, _ = is_blocked("2024-02-02 22:00", events, before_min=30, after_min=30)
    assert blocked  # 30 min before high-impact -> blocked
    blocked, _ = is_blocked("2024-02-02 23:30", events, before_min=30, after_min=30)
    assert not blocked  # 60 min after -> allowed (window is +/-30)
    blocked, _ = is_blocked("2024-02-01 12:05", events, before_min=30, after_min=30)
    assert not blocked  # near medium-impact -> allowed (only high blocks by default)
    blocked, _ = is_blocked("2024-02-03 09:00", events, before_min=30, after_min=30)
    assert not blocked  # clear


def test_filter_times_splits_correctly():
    events = [{"time": "2024-02-02 22:30", "impact": "high"}]
    candidates = ["2024-02-02 22:00", "2024-02-02 23:30"]
    allowed, blocked = filter_times(candidates, events, before_min=30, after_min=30)
    assert len(allowed) == 1 and len(blocked) == 1


class _AlwaysLong:
    """Trivial strategy: go long the instant we're flat. Used to isolate the
    news filter's effect on entries."""
    warmup = 0

    def signal(self, history, position=0):
        return 1


def _flat_df(n, start="2024-01-01 00:00", freq="h", price=100.0):
    times = pd.date_range(start, periods=n, freq=freq)
    return pd.DataFrame({"timestamp": times, "open": price, "high": price,
                          "low": price, "close": price})


def test_engine_blocks_new_entries_during_news_window():
    df = _flat_df(6)  # bars at 00:00 .. 05:00
    # blocks [01:00, 02:00] inclusive -> the bar-1 and bar-2 entry opportunities
    events = [{"time": "2024-01-01 01:30", "impact": "high"}]
    config = BacktestConfig(events=events, news_before_min=30, news_after_min=30)
    trades, summary = run_backtest(df, _AlwaysLong(), config)

    assert summary["skipped_news"] == 2
    assert len(trades) == 1
    # first allowed opportunity is bar index 3 (03:00), entered at its open
    assert trades.iloc[0]["entry_time"] == pd.Timestamp("2024-01-01 03:00:00")


class _FlipAtFourBars:
    """Long until 4 closed bars have accumulated, then flip flat and stay flat."""
    warmup = 0

    def signal(self, history, position=0):
        if len(history) >= 4:
            return 0
        return 1


def test_engine_never_blocks_exits_during_news_window():
    df = _flat_df(8)  # bars at 00:00 .. 07:00
    # blocks exactly the bar (04:00) where the signal-flip exit would execute
    events = [{"time": "2024-01-01 04:00", "impact": "high"}]
    config = BacktestConfig(events=events, news_before_min=30, news_after_min=30)
    trades, summary = run_backtest(df, _FlipAtFourBars(), config)

    assert len(trades) == 1
    assert trades.iloc[0]["reason"] == "signal"
    assert trades.iloc[0]["exit_time"] == pd.Timestamp("2024-01-01 04:00:00")
    assert summary["skipped_news"] == 0  # the event never overlapped an entry attempt


if __name__ == "__main__":
    test_is_blocked_matches_skill_example()
    test_filter_times_splits_correctly()
    test_engine_blocks_new_entries_during_news_window()
    test_engine_never_blocks_exits_during_news_window()
    print("OK: all news filter tests passed")
