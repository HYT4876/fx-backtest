"""run_example.py — end-to-end demo: compare the three strategy families.

Generates synthetic data (trend + ranging regimes), also saves it as a CSV so the
real-data path (data.py -> run_backtest.py) can be exercised, then runs all three
strategies through the look-ahead-safe engine with costs and prints metrics.

The synthetic data and toy strategies are NOT profitable systems — they exercise
the plumbing. Per fx-project-rules, judge on out-of-sample stability, not headline
profit.
"""

import numpy as np
import pandas as pd

from engine import run_backtest, BacktestConfig
from costs import CostModel
from strategy import MACrossStrategy, MeanReversionStrategy, BreakoutStrategy
from walkforward import walk_forward_windows


def make_synthetic(n=3000, seed=7, start=150.0):
    rng = np.random.default_rng(seed)
    drift = np.concatenate([
        np.full(n // 3, 0.02), np.full(n // 3, -0.015),
        np.full(n - 2 * (n // 3), 0.01),
    ])
    steps = drift + rng.normal(0, 0.15, n)
    close = np.maximum(start + np.cumsum(steps), 1.0)
    times = pd.date_range("2023-01-01", periods=n, freq="h")
    high = close + np.abs(rng.normal(0, 0.08, n))
    low = close - np.abs(rng.normal(0, 0.08, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"timestamp": times, "open": open_, "high": high, "low": low, "close": close})


def metrics_line(trades_df, start_balance):
    if trades_df.empty:
        return "取引なし"
    pnls = trades_df["net_pnl"].values
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    equity = start_balance + np.cumsum(pnls)
    dd = (equity - np.maximum.accumulate(equity)).min()
    return (f"取引{len(pnls):>3} | 勝率{len(wins)/len(pnls)*100:4.0f}% | "
            f"期待値{pnls.mean():>7,.0f} | PF{pf:4.2f} | "
            f"net{pnls.sum():>9,.0f} | DD{dd:>9,.0f}")


def main():
    df = make_synthetic()
    df.to_csv("sample_data.csv", index=False)  # for testing run_backtest.py
    print("サンプルデータを sample_data.csv に保存しました。\n")

    config = BacktestConfig(
        account=300_000, risk_pct=1.0, stop_pips=50, pip_size=0.01,
        costs=CostModel(spread_pips=0.5, slippage_pips=0.3,
                        swap_per_10k_per_night=-15.0, pip_value_per_unit=0.01),
    )
    strategies = {
        "順張り(MAクロス)": MACrossStrategy(20, 50),
        "逆張り(平均回帰)": MeanReversionStrategy(50, 2.0, 0.0),
        "ブレイクアウト":   BreakoutStrategy(50, 20),
    }

    print("=== 全期間バックテスト（コスト込み・合成データ）===")
    for name, strat in strategies.items():
        trades, _ = run_backtest(df, strat, config)
        print(f"  {name:<16}: {metrics_line(trades, config.account)}")

    print("\n=== ウォークフォワード（学習1000/検証500）— 順張りの例 ===")
    for k, (train, test) in enumerate(walk_forward_windows(df, 1000, 500), 1):
        t_tr, _ = run_backtest(train, MACrossStrategy(20, 50), config)
        t_te, _ = run_backtest(test, MACrossStrategy(20, 50), config)
        tr = t_tr["net_pnl"].sum() if len(t_tr) else 0
        te = t_te["net_pnl"].sum() if len(t_te) else 0
        print(f"  巡目{k}: 学習net {tr:>10,.0f} | 検証net {te:>10,.0f}")
    print("\n（検証期間でも安定して成績が出るかが、過学習していない証拠）")


if __name__ == "__main__":
    main()
