"""costs.py — trading cost model (mirrors the backtest-cost-model skill).

A backtest without spread/slippage/commission/swap lies. Keep assumptions
conservative.
"""

from dataclasses import dataclass


@dataclass
class CostModel:
    spread_pips: float = 0.5
    slippage_pips: float = 0.3        # per side
    commission_per_10k: float = 0.0
    swap_per_10k_per_night: float = 0.0   # signed: + received, - paid
    pip_value_per_unit: float = 0.01

    def round_trip_cost(self, units, nights_held=0):
        u = abs(units)
        spread = self.spread_pips * self.pip_value_per_unit * u
        slippage = self.slippage_pips * 2 * self.pip_value_per_unit * u
        commission = self.commission_per_10k * (u / 10000.0)
        swap = self.swap_per_10k_per_night * (u / 10000.0) * nights_held
        return spread + slippage + commission - swap

    def net_pnl(self, gross_pnl, units, nights_held=0):
        return gross_pnl - self.round_trip_cost(units, nights_held)
