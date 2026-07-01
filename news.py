"""news.py — block NEW entries around high-impact economic events (mirrors
the news-filter skill).

Major scheduled events (NFP, FOMC, BOJ, CPI...) cause spread blowouts,
slippage, and gaps — exactly when an automated system gets hurt. The safe
default is not to predict the news but to avoid opening new risk around it.

This does NOT fetch a calendar. Events are supplied as a list of dicts
{"time": <datetime/str>, "impact": "high"|"medium"|"low"} or loaded from a
CSV with `time,impact` columns (see load_events_csv). Timezone must match
whatever the candle data was standardized to (e.g. JST after --tz-shift).

Only NEW entries are blocked — an open position's stop-loss and signal-flip
exit still fire during a blocked window. Pausing risk management during news
would be the opposite of what this filter is for.
"""

from datetime import datetime, timedelta
import pandas as pd


def _to_dt(x):
    return x if isinstance(x, datetime) else pd.to_datetime(x).to_pydatetime()


def is_blocked(t, events, before_min=30, after_min=30, block_impacts=("high",)):
    """Return (blocked: bool, reason: str|None) for timestamp t given events."""
    t = _to_dt(t)
    for ev in events:
        if ev.get("impact", "low") not in block_impacts:
            continue
        et = _to_dt(ev["time"])
        if et - timedelta(minutes=before_min) <= t <= et + timedelta(minutes=after_min):
            return True, f"blocked by {ev.get('impact')} event at {et:%Y-%m-%d %H:%M}"
    return False, None


def filter_times(candidate_times, events, before_min=30, after_min=30, block_impacts=("high",)):
    """Split candidate entry times into allowed and blocked."""
    allowed, blocked = [], []
    for t in candidate_times:
        is_b, reason = is_blocked(t, events, before_min, after_min, block_impacts)
        (blocked if is_b else allowed).append((t, reason))
    return allowed, blocked


def load_events_csv(path):
    """Load a calendar CSV with `time,impact` columns (case-insensitive) into
    the event-dict list this module expects. Timezone must already match the
    candle data (align it yourself before saving the CSV)."""
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    for required in ("time", "impact"):
        if required not in cols:
            raise ValueError(f"events CSV is missing required column: {required}")
    return [
        {"time": row[cols["time"]], "impact": str(row[cols["impact"]]).lower()}
        for _, row in df.iterrows()
    ]
