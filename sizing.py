"""sizing.py — position sizing (mirrors the position-sizing skill).

Size is decided by formula, never by feel. Hitting the stop loses exactly the
intended risk amount.
"""


def compute_position(account, risk_pct, stop_pips, entry,
                     pip_size=0.01, quote_to_account_rate=1.0, max_leverage=25.0):
    if account <= 0 or risk_pct <= 0 or stop_pips <= 0 or entry <= 0:
        raise ValueError("account, risk_pct, stop_pips, entry must all be positive")
    risk_amount = account * (risk_pct / 100.0)
    loss_per_unit = stop_pips * pip_size * quote_to_account_rate
    units = risk_amount / loss_per_unit
    notional = units * entry * quote_to_account_rate
    leverage = notional / account
    return {
        "units": units,
        "notional": notional,
        "leverage": leverage,
        "exceeds_cap": leverage > max_leverage,
    }
