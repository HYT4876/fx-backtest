"""data.py — load and clean OHLC data for the engine.

Supports two input formats:
  - "standard": a CSV with columns timestamp, open, high, low, close (+ optional volume)
  - "histdata_m1": HistData.com Generic ASCII M1 files
        no header, semicolon-separated, datetime as `YYYYMMDD HHMMSS`:
        20230102 000000;150.000;150.020;149.990;150.005;0

Both flow through the same cleaning (mirrors the data-cleaning skill): drop bad
timestamps, dedupe, sort, remove non-positive/NaN prices, fix OHLC integrity,
flag spikes. Weekend gaps (normal in FX) are NOT filled. Ragged/bad rows are
skipped on read.

Timezone note: HistData M1 timestamps are Eastern Standard Time (no DST). Use
`tz_shift_hours` to shift into the timezone you standardize on (align it with
your candle data and the news-filter event times — mismatches cause silent bugs).
"""

import numpy as np
import pandas as pd

_PRICE_COLS = ["open", "high", "low", "close"]


def _clean(df, spike_sigma=8.0, verbose=True):
    """Clean a DataFrame that already has standard columns."""
    n0 = len(df)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    df = df.drop_duplicates(subset="timestamp", keep="last")

    for c in _PRICE_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[~(df[_PRICE_COLS].isna().any(axis=1) | (df[_PRICE_COLS] <= 0).any(axis=1))]

    hi = df[_PRICE_COLS].max(axis=1)
    lo = df[_PRICE_COLS].min(axis=1)
    df["high"] = np.maximum(df["high"], hi)
    df["low"] = np.minimum(df["low"], lo)

    ret = df["close"].pct_change()
    sigma = ret.std()
    df["spike_flag"] = (ret.abs() > spike_sigma * sigma).fillna(False) if sigma and sigma > 0 else False

    df = df.reset_index(drop=True)
    if verbose and len(df):
        print(f"[data] {n0:,} rows -> cleaned {len(df):,} "
              f"({df['timestamp'].min()} .. {df['timestamp'].max()}), "
              f"{int(df['spike_flag'].sum())} spike(s) flagged")
    return df


def load_and_clean(csv_path, spike_sigma=8.0, verbose=True):
    """Load a standard CSV (timestamp, open, high, low, close[, volume])."""
    df = pd.read_csv(csv_path, on_bad_lines="skip")
    cols = {c.lower(): c for c in df.columns}
    required = ["timestamp", "open", "high", "low", "close"]
    missing = [c for c in required if c not in cols]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    df = df.rename(columns={cols[c]: c for c in cols})
    return _clean(df, spike_sigma, verbose)


def load_histdata_m1(path, tz_shift_hours=0, spike_sigma=8.0, verbose=True):
    """Load a HistData.com Generic ASCII M1 file and convert to standard form.

    Format: no header, datetime `YYYYMMDD HHMMSS`, then O;H;L;C;V. Separator is
    usually ';' but ',' is auto-detected as a fallback.
    """
    # auto-detect separator from the first line
    with open(path, "r") as f:
        first = f.readline()
    sep = ";" if first.count(";") >= first.count(",") else ","

    df = pd.read_csv(path, sep=sep, header=None, on_bad_lines="skip",
                     names=["datetime", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["datetime"], format="%Y%m%d %H%M%S", errors="coerce")
    if tz_shift_hours:
        df["timestamp"] = df["timestamp"] + pd.Timedelta(hours=tz_shift_hours)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    return _clean(df, spike_sigma, verbose)


def resample_ohlc(df, rule, verbose=True):
    """Resample a cleaned standard-form df (timestamp, OHLC[, volume]) to a
    coarser bar size, e.g. "1h", "4h", "1D". Uses only closed-bar aggregation
    (open=first, high=max, low=min, close=last), so no look-ahead is introduced.
    Bars with no ticks in the window (e.g. weekend gaps) are dropped, not filled.
    """
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    out = (df.set_index("timestamp")
             .resample(rule)
             .agg(agg)
             .dropna(subset=["open", "high", "low", "close"])
             .reset_index())
    if verbose:
        print(f"[data] resampled to {rule}: {len(df):,} -> {len(out):,} bars")
    return out
