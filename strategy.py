"""strategy.py — strategy interface and example strategies.

A Strategy answers ONE question at each closed bar: given everything known up to
and including this bar (and the engine's current position), do we want to be
long (+1) or flat (0)? The engine executes the resulting order on the NEXT bar.

Look-ahead safety: signal() must only read `history` (closed bars). It must not
peek at future bars. Comparing the current closed bar's values to PRIOR bars is
fine; using a future bar is not.

The `position` argument (0 flat, 1 long) lets a strategy use hysteresis — e.g.
mean-reversion enters when oversold but holds until price reverts to the mean.

These edges are deliberately simple; they exist to exercise the engine. Per
fx-project-rules, always ask "why does this make money?" before trusting any of
them. They map to the three families discussed: trend-following, mean-reversion,
breakout.
"""


class Strategy:
    warmup = 0

    def signal(self, history, position=0):
        """Return +1 (want long) or 0 (want flat). Read only `history`."""
        raise NotImplementedError


class MACrossStrategy(Strategy):
    """Trend-following: long when fast MA is above slow MA; flat otherwise."""

    def __init__(self, fast=20, slow=50):
        if fast >= slow:
            raise ValueError("fast period must be shorter than slow period")
        self.fast, self.slow = fast, slow
        self.warmup = slow

    def signal(self, history, position=0):
        if len(history) < self.slow:
            return 0
        closes = history["close"]
        fast_ma = closes.iloc[-self.fast:].mean()
        slow_ma = closes.iloc[-self.slow:].mean()
        return 1 if fast_ma > slow_ma else 0


class MeanReversionStrategy(Strategy):
    """Mean-reversion (逆張り): buy when price is deeply below its rolling mean
    (oversold), then HOLD until it reverts back toward the mean.

    Uses a z-score: z = (close - rolling_mean) / rolling_std.
    Enter long when z < -entry_z. Hold until z >= exit_z (default 0 = the mean).
    Hysteresis (different entry/exit thresholds) needs the position argument.
    """

    def __init__(self, window=50, entry_z=2.0, exit_z=0.0):
        if window < 2:
            raise ValueError("window must be >= 2")
        self.window, self.entry_z, self.exit_z = window, entry_z, exit_z
        self.warmup = window

    def _zscore(self, history):
        closes = history["close"].iloc[-self.window:]
        mean = closes.mean()
        std = closes.std()
        if not std or std == 0:
            return 0.0
        return (history["close"].iloc[-1] - mean) / std

    def signal(self, history, position=0):
        if len(history) < self.window:
            return 0
        z = self._zscore(history)
        if position == 0:
            return 1 if z < -self.entry_z else 0      # enter when oversold
        else:
            return 0 if z >= self.exit_z else 1       # hold until reverted to mean


class BreakoutStrategy(Strategy):
    """Breakout: long when the current close breaks above the high of the prior
    `lookback` bars; exit when it breaks below the low of the prior `exit_lookback`
    bars. Long-only.
    """

    def __init__(self, lookback=50, exit_lookback=20):
        self.lookback, self.exit_lookback = lookback, exit_lookback
        self.warmup = max(lookback, exit_lookback) + 1

    def signal(self, history, position=0):
        if len(history) < self.warmup:
            return 0
        close = history["close"].iloc[-1]
        if position == 0:
            prior_high = history["high"].iloc[-(self.lookback + 1):-1].max()
            return 1 if close > prior_high else 0
        else:
            prior_low = history["low"].iloc[-(self.exit_lookback + 1):-1].min()
            return 0 if close < prior_low else 1
