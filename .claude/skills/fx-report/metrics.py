"""metrics.py — fx-report スキルの指標計算。

trades CSV（最低 net_pnl 列）からリスク指標を計算して表示する。
run_backtest.py の print_metrics と同じ定義を使う（コスト込みの net_pnl が前提）。

    python3 metrics.py trades.csv --account 300000
"""

import argparse
import numpy as np
import pandas as pd


def compute(pnls, start_balance):
    pnls = np.asarray(pnls, dtype=float)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    gp, gl = wins.sum(), -losses.sum()
    equity = start_balance + np.cumsum(pnls)
    dd = (equity - np.maximum.accumulate(equity)).min()
    pf = gp / gl if gl > 0 else float("inf")
    return {
        "trades": len(pnls),
        "win_rate": len(wins) / len(pnls) if len(pnls) else 0.0,
        "expectancy": pnls.mean() if len(pnls) else 0.0,
        "net": pnls.sum(),
        "pf": pf,
        "max_dd": dd if len(pnls) else 0.0,
    }


def main():
    p = argparse.ArgumentParser(description="trades CSV から成績指標を計算")
    p.add_argument("csv", help="net_pnl 列を持つ取引CSV")
    p.add_argument("--account", type=float, default=300_000)
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    if "net_pnl" not in df.columns or df.empty:
        print("取引なし（net_pnl 列が無い、または0件）— 期間・パラメータを確認")
        return

    m = compute(df["net_pnl"].values, args.account)
    pf = "∞" if not np.isfinite(m["pf"]) else f"{m['pf']:.2f}"
    print(f"取引回数:               {m['trades']}")
    print(f"勝率:                   {m['win_rate']*100:.1f}%")
    print(f"期待値(1取引):          {m['expectancy']:,.1f}")
    print(f"総損益(net):            {m['net']:,.0f}")
    print(f"プロフィットファクター: {pf}")
    print(f"最大ドローダウン:       {m['max_dd']:,.0f}")
    if m["expectancy"] <= 0:
        print("⚠ 期待値がプラスでない（fx-project-rules: 採用しない）")


if __name__ == "__main__":
    main()
