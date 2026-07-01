"""run_backtest.py — run a backtest on a real OHLC CSV from the command line.

Loads and cleans the CSV (data.py), runs the chosen strategy through the
look-ahead-safe engine with costs and position sizing, and prints metrics.

Usage:
    python run_backtest.py data/usdjpy_1h.csv --strategy ma_cross
    python run_backtest.py data/usdjpy_1h.csv --strategy mean_reversion --risk-pct 1 --stop-pips 40
    python run_backtest.py data/eurusd_1h.csv --strategy breakout --pip-size 0.0001 --quote-rate 150
    python run_backtest.py DAT_ASCII_USDJPY_M1_2025.csv --format histdata_m1 --tz-shift 14 --resample 1h

Strategies: ma_cross | mean_reversion | breakout
"""

import argparse
import numpy as np

from data import load_and_clean, load_histdata_m1, resample_ohlc
from engine import run_backtest, BacktestConfig
from costs import CostModel
from news import load_events_csv
from strategy import MACrossStrategy, MeanReversionStrategy, BreakoutStrategy


def build_strategy(name):
    if name == "ma_cross":
        return MACrossStrategy(fast=20, slow=50)
    if name == "mean_reversion":
        return MeanReversionStrategy(window=50, entry_z=2.0, exit_z=0.0)
    if name == "breakout":
        return BreakoutStrategy(lookback=50, exit_lookback=20)
    raise ValueError(f"unknown strategy: {name}")


def print_metrics(trades_df, start_balance, summary=None):
    if trades_df.empty:
        print("  (取引なし — データ期間や戦略パラメータを確認)")
        if summary and summary.get("skipped_leverage_cap"):
            print(f"  レバ上限超でスキップ:   {summary['skipped_leverage_cap']}件（全エントリーがこれで消えた可能性）")
        return
    pnls = trades_df["net_pnl"].values
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    gp, gl = wins.sum(), -losses.sum()
    equity = start_balance + np.cumsum(pnls)
    dd = equity - np.maximum.accumulate(equity)
    pf = gp / gl if gl > 0 else float("inf")
    print(f"  取引回数:               {len(pnls)}")
    print(f"  勝率:                   {len(wins)/len(pnls)*100:.1f}%")
    print(f"  期待値(1取引):          {pnls.mean():,.1f}")
    print(f"  総損益(net):            {pnls.sum():,.0f}")
    print(f"  プロフィットファクター: {pf:.2f}" if np.isfinite(pf) else "  プロフィットファクター: ∞")
    print(f"  最大ドローダウン:       {dd.min():,.0f}")
    if summary and summary.get("skipped_leverage_cap"):
        print(f"  レバ上限超でスキップ:   {summary['skipped_leverage_cap']}件（機会損失として認識）")
    if summary and summary.get("skipped_news"):
        print(f"  ニュースでスキップ:     {summary['skipped_news']}件（新規エントリーのみ停止）")
    if pnls.mean() <= 0:
        print("  ⚠ 期待値がプラスでない（fx-project-rules: 採用しない）")


def main():
    p = argparse.ArgumentParser(description="Run a backtest on a real OHLC CSV.")
    p.add_argument("csv")
    p.add_argument("--strategy", default="ma_cross",
                   choices=["ma_cross", "mean_reversion", "breakout"])
    p.add_argument("--format", default="standard", choices=["standard", "histdata_m1"],
                   help="standard CSV, or HistData.com Generic ASCII M1")
    p.add_argument("--tz-shift", type=float, default=0.0,
                   help="shift timestamps by N hours (HistData M1 is EST; align to your TZ)")
    p.add_argument("--resample", default=None,
                   help="resample to a coarser bar size before backtesting, e.g. 1h, 4h, 1D")
    p.add_argument("--account", type=float, default=300_000)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--stop-pips", type=float, default=50.0)
    p.add_argument("--pip-size", type=float, default=0.01)
    p.add_argument("--quote-rate", type=float, default=1.0,
                   help="quote->account rate (1.0 for JPY account on *JPY pairs)")
    p.add_argument("--spread-pips", type=float, default=0.5)
    p.add_argument("--slippage-pips", type=float, default=0.3)
    p.add_argument("--swap-per-10k", type=float, default=0.0)
    p.add_argument("--events", default=None,
                   help="calendar CSV (time,impact columns) to block new entries around "
                        "high-impact events; timestamps must match the data's timezone")
    p.add_argument("--news-before-min", type=float, default=30.0)
    p.add_argument("--news-after-min", type=float, default=30.0)
    args = p.parse_args()

    if args.format == "histdata_m1":
        df = load_histdata_m1(args.csv, tz_shift_hours=args.tz_shift)
    else:
        df = load_and_clean(args.csv)
    if args.resample:
        df = resample_ohlc(df, args.resample)
    events = load_events_csv(args.events) if args.events else []
    config = BacktestConfig(
        account=args.account, risk_pct=args.risk_pct, stop_pips=args.stop_pips,
        pip_size=args.pip_size, quote_to_account_rate=args.quote_rate,
        costs=CostModel(spread_pips=args.spread_pips, slippage_pips=args.slippage_pips,
                        swap_per_10k_per_night=args.swap_per_10k,
                        pip_value_per_unit=args.pip_size * args.quote_rate),
        events=events, news_before_min=args.news_before_min, news_after_min=args.news_after_min,
    )
    strat = build_strategy(args.strategy)
    print(f"\n=== バックテスト: {args.strategy}（コスト込み）===")
    trades, summary = run_backtest(df, strat, config)
    print_metrics(trades, args.account, summary)


if __name__ == "__main__":
    main()
