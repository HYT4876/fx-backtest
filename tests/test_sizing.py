"""test_sizing.py — regression check for compute_position unit conversions.

Confirms quote_to_account_rate is applied once each to two distinct
quantities (loss_per_unit, notional), not double-counted on one value.
Verified by independent hand-calculation for both a JPY-cross pair
(quote currency == account currency) and a non-JPY-cross pair traded
on a JPY account (quote_to_account_rate != 1.0).

Run: python3 tests/test_sizing.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sizing import compute_position


def test_usdjpy_jpy_account():
    # risk=3000 JPY, loss/unit=50*0.01*1=0.5 JPY/USD -> units=6000 USD
    # notional=6000*150*1=900,000 JPY, leverage=3.0
    r = compute_position(account=300_000, risk_pct=1, stop_pips=50, entry=150.0,
                          pip_size=0.01, quote_to_account_rate=1.0)
    assert r["units"] == 6000.0
    assert r["notional"] == 900_000.0
    assert abs(r["leverage"] - 3.0) < 1e-9
    assert not r["exceeds_cap"]


def test_eurusd_on_jpy_account():
    # risk=3000 JPY, loss/unit=50*0.0001*150=0.75 JPY/EUR -> units=4000 EUR
    # 4000 EUR -> 4400 USD (at entry 1.10) -> 660,000 JPY (at USDJPY=150)
    r = compute_position(account=300_000, risk_pct=1, stop_pips=50, entry=1.10,
                          pip_size=0.0001, quote_to_account_rate=150)
    assert r["units"] == 4000.0
    assert abs(r["notional"] - 660_000.0) < 1e-6
    assert abs(r["leverage"] - 2.2) < 1e-9
    assert not r["exceeds_cap"]


def test_leverage_cap_is_respected():
    # tiny stop -> huge units -> leverage should exceed 25x and be flagged
    r = compute_position(account=300_000, risk_pct=1, stop_pips=1, entry=150.0,
                          pip_size=0.01, quote_to_account_rate=1.0)
    assert r["exceeds_cap"]


if __name__ == "__main__":
    test_usdjpy_jpy_account()
    test_eurusd_on_jpy_account()
    test_leverage_cap_is_respected()
    print("OK: all sizing tests passed")
