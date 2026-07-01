# fx-backtest — バックテスト雛形

FX自動売買システムの土台。**ルックアヘッドを出さない**バックテストエンジンの最小実装で、これまで作ったスキル（資金管理・コストモデル・データ整形・評価指標・ニュース回避・設計原則）が実際に噛み合う場所です。

## これは何で、何でないか

- これは「学習と反復のための雛形」です。1通貨・ロングのみ・1ポジションずつの最小構成。
- サンプル戦略と合成データは、配管が正しく繋がることを確認するためのもので、**儲かるシステムではありません**。
- `fx-project-rules` の通り、戦略を信じる前に必ず「なぜ儲かるのか？」を問うこと。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `engine.py` | バックテスト本体。判断はバー確定後、約定は次のバー（ルックアヘッド防止）。損切り必須・コスト計上・レバ25倍超はスキップ。 |
| `strategy.py` | 戦略インターフェースと3つのサンプル戦略（順張り・逆張り・ブレイクアウト）。 |
| `sizing.py` | ポジションサイズ計算（`position-sizing` スキルと同ロジック）。 |
| `costs.py` | スプレッド・スリッページ・手数料・スワップ（`backtest-cost-model` スキルと同ロジック）。 |
| `data.py` | OHLCデータの読み込み＋クリーニング。標準CSVと HistData.com Generic ASCII M1 の両形式に対応。不正行スキップ・週末ギャップは埋めない・タイムゾーンシフト対応。 |
| `walkforward.py` | 学習期間／検証期間に分けて前へずらす分割。 |
| `run_example.py` | 合成データで3戦略を比較するデモ。`sample_data.csv` も書き出す。 |
| `run_backtest.py` | 実データCSVでバックテストを回すCLI。 |

## 動かし方

```bash
pip install pandas numpy

# 1) 合成データで3戦略を比較（sample_data.csv も生成される）
python run_example.py

# 2) 実データCSVでバックテスト
python run_backtest.py your_data.csv --strategy ma_cross
python run_backtest.py your_data.csv --strategy mean_reversion --risk-pct 1 --stop-pips 40
python run_backtest.py your_data.csv --strategy breakout
# 非対円ペア（例 EUR/USD, JPY口座, USDJPY=150）
python run_backtest.py eurusd.csv --strategy ma_cross --pip-size 0.0001 --quote-rate 150
```

CSVの必須列（大文字小文字不問）: `timestamp, open, high, low, close`（任意で `volume`）。

## 実データの入手と取り込み

無料の入手先の例：
- HistData.com — USD/JPY等の1分足・ティックを無料配布（Generic ASCII形式）。手軽に始めるならここ。
- Dukascopy（`dukascopy_python` 等）— bid/ask付きティック。スプレッドを含むコストを正確にモデル化できる。本格バックテスト向け。
- Twelve Data / Alpha Vantage — API取得。自動更新を組むとき。

HistData.com の1分足（Generic ASCII M1）は専用ローダーで直接読める：

```bash
# HistData形式（日時 YYYYMMDD HHMMSS・セミコロン区切り・ヘッダ無し）
python run_backtest.py DAT_ASCII_USDJPY_M1_2023.csv --format histdata_m1 --tz-shift 14
```

注意点（設計に直結）：
- フォーマット：日付と時刻が別列の形式は、`timestamp` 1列に結合してから渡す。
- タイムゾーン：HistData M1 は EST（夏時間なし）。`--tz-shift` で自分の基準（JST等）に揃える。データ・ローソク足・`news-filter` のイベント時刻を必ず同一基準に。
- 業者差：無料データは一般的なバックテスト用で、自分の業者の価格とは一致しない。最終検証は実際に使う業者のデータで行うのが理想。

## 3つの戦略（型）

| 戦略 | 哲学 | 効く相場 |
|---|---|---|
| `ma_cross` | 順張り（トレンドフォロー）：動き出したら続くに賭ける | 強いトレンド |
| `mean_reversion` | 逆張り：行き過ぎは平均へ戻るに賭ける | レンジ |
| `breakout` | 高値抜けで入る | トレンド発生の初動 |

万能な戦略は無い。`run_example.py` の出力でも、トレンド寄りの合成データでは順張り・ブレイクアウトが勝ち、逆張りが負ける（相場の地合いと戦略の相性がそのまま出る）。

## 設計の肝（ここを崩さない）

- ルックアヘッド防止：バー `i` の確定情報だけで判断し、約定は `i+1` の始値。そのバー自身の終値・高値・安値を、同じバー内の判断に使わない。
- 損切り必須：全ポジションに損切りを置き、損失が許容額（資金のリスク%）に一致するようサイズを決める。
- コスト常時計上：粗損益は必ず `CostModel.net_pnl` を通す。
- レバレッジ上限：実効レバレッジが25倍を超えるエントリーはスキップ。スキップ件数は `summary["skipped_leverage_cap"]`（CLIでも表示）で確認でき、黙って機会損失にならないようにしている。

## このあとの拡張（順序の目安）

1. 実データを取り込む（`run_backtest.py` か `data.load_and_clean` 経由）。
2. `news-filter` をエントリー条件に組み込む（重要イベント前後は新規取引停止）。
3. `performance-metrics` で検証期間の成績を評価し、ウォークフォワードで安定性を確認。
4. ショート対応・複数ポジション・複数通貨へ慎重に拡張（パラメータは増やしすぎない）。
5. デモ口座で長期ペーパートレード → ごく小額の実運用 → 監視・キルスイッチ。

機械学習は最後の工程。価格予測より、リスク管理・ポジションサイジングの調整に効かせるほうが安定する。

## 注意

これは技術的な雛形であり、投資助言ではありません。実運用は完全に自己責任で、必ずデモか小額から始めてください。
