"""run_walkforward.py — walk-forward validation on a real OHLC CSV.

Loads and cleans real data (data.py), optionally resamples to a coarser bar
size, then rolls train/test windows forward (walkforward.py) and runs the
chosen strategy through the look-ahead-safe engine on each window. Judge on
whether test-window performance holds up across folds, not on in-sample
profit (fx-project-rules: a strategy that only looks good in-sample is overfit).

Usage:
    python run_walkforward.py DAT_ASCII_USDJPY_M1_2025.csv \
        --format histdata_m1 --tz-shift 14 --resample 1h \
        --strategy ma_cross --train 2000 --test 500
"""

import argparse
import numpy as np

from data import load_and_clean, load_histdata_m1, resample_ohlc
from engine import run_backtest, BacktestConfig
from costs import CostModel
from walkforward import walk_forward_windows
from run_backtest import build_strategy


def fold_line(trades_df, start_balance):
    if trades_df.empty:
        return "取引なし"
    pnls = trades_df["net_pnl"].values
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    equity = start_balance + np.cumsum(pnls)
    dd = (equity - np.maximum.accumulate(equity)).min()
    pf_str = f"{pf:4.2f}" if np.isfinite(pf) else " inf"
    return (f"取引{len(pnls):>4} | 勝率{len(wins)/len(pnls)*100:4.0f}% | "
            f"期待値{pnls.mean():>8,.0f} | PF{pf_str} | "
            f"net{pnls.sum():>10,.0f} | DD{dd:>10,.0f}")


def main():
    p = argparse.ArgumentParser(description="Walk-forward validation on a real OHLC CSV.")
    p.add_argument("csv")
    p.add_argument("--strategy", default="ma_cross",
                   choices=["ma_cross", "mean_reversion", "breakout"])
    p.add_argument("--format", default="standard", choices=["standard", "histdata_m1"])
    p.add_argument("--tz-shift", type=float, default=0.0)
    p.add_argument("--resample", default=None,
                   help="resample to a coarser bar size before splitting, e.g. 1h, 4h, 1D")
    p.add_argument("--train", type=int, default=2000, help="train window size in bars")
    p.add_argument("--test", type=int, default=500, help="test window size in bars")
    p.add_argument("--account", type=float, default=300_000)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--stop-pips", type=float, default=50.0)
    p.add_argument("--pip-size", type=float, default=0.01)
    p.add_argument("--quote-rate", type=float, default=1.0)
    p.add_argument("--spread-pips", type=float, default=0.5)
    p.add_argument("--slippage-pips", type=float, default=0.3)
    p.add_argument("--swap-per-10k", type=float, default=0.0)
    args = p.parse_args()

    if args.format == "histdata_m1":
        df = load_histdata_m1(args.csv, tz_shift_hours=args.tz_shift)
    else:
        df = load_and_clean(args.csv)
    if args.resample:
        df = resample_ohlc(df, args.resample)

    config = BacktestConfig(
        account=args.account, risk_pct=args.risk_pct, stop_pips=args.stop_pips,
        pip_size=args.pip_size, quote_to_account_rate=args.quote_rate,
        costs=CostModel(spread_pips=args.spread_pips, slippage_pips=args.slippage_pips,
                        swap_per_10k_per_night=args.swap_per_10k,
                        pip_value_per_unit=args.pip_size * args.quote_rate),
    )

    print(f"\n=== ウォークフォワード: {args.strategy}（学習{args.train}本/検証{args.test}本）===")
    folds = list(walk_forward_windows(df, args.train, args.test))
    if not folds:
        print(f"  データが足りません（{len(df)}本 < 学習+検証={args.train + args.test}本）")
        return

    test_nets = []
    for k, (train, test) in enumerate(folds, 1):
        strat_train = build_strategy(args.strategy)
        strat_test = build_strategy(args.strategy)
        t_tr, _ = run_backtest(train, strat_train, config)
        t_te, _ = run_backtest(test, strat_test, config)
        test_nets.append(t_te["net_pnl"].sum() if len(t_te) else 0.0)
        print(f"  巡目{k:>2}: 学習 {fold_line(t_tr, args.account)}")
        print(f"        検証 {fold_line(t_te, args.account)}")

    positive = sum(1 for n in test_nets if n > 0)
    print(f"\n検証期間で net がプラスだった巡目: {positive}/{len(test_nets)}")
    if positive < len(test_nets) / 2:
        print("⚠ 過半数の検証期間でマイナス（fx-project-rules: 安定性を疑うべき）")


if __name__ == "__main__":
    main()
