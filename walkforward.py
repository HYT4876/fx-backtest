"""walkforward.py — split data into rolling in-sample / out-of-sample windows.

Optimize on the in-sample window, evaluate on the out-of-sample window the
strategy never saw. Roll forward and repeat. A strategy that only looks good
in-sample is overfit (fx-project-rules).
"""


def walk_forward_windows(df, train_size, test_size, step=None):
    """Yield (train_df, test_df) tuples rolling forward over df by `step` rows
    (defaults to test_size, i.e. non-overlapping test windows)."""
    step = step or test_size
    n = len(df)
    start = 0
    while start + train_size + test_size <= n:
        train = df.iloc[start: start + train_size]
        test = df.iloc[start + train_size: start + train_size + test_size]
        yield train.reset_index(drop=True), test.reset_index(drop=True)
        start += step
