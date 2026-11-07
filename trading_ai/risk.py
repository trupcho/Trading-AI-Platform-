"""Pure risk checks for synthetic/paper simulations and regression testing.

EA separately implements broker-aware validation. Monetary conversion must come
from MT5 OrderCalcProfit and never from assumed tick values.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class AccountRisk:
    equity_eur: Decimal = Decimal("500")
    risk_fraction: Decimal = Decimal("0.0025")
    daily_loss_fraction: Decimal = Decimal("0.01")
    max_positions: int = 1
    max_margin_fraction: Decimal = Decimal("0.35")

    @property
    def risk_budget_eur(self) -> Decimal:
        return self.equity_eur * self.risk_fraction


@dataclass(frozen=True)
class Candidate:
    loss_eur_per_lot_at_sl: Decimal
    min_lot: Decimal
    lot_step: Decimal
    max_lot: Decimal
    margin_eur_per_lot: Decimal
    current_positions: int
    daily_equity_start_eur: Decimal
    current_equity_eur: Decimal
    spread_ok: bool
    market_open: bool


def permitted_volume(risk: AccountRisk, trade: Candidate) -> tuple[Decimal, str]:
    if trade.current_positions >= risk.max_positions:
        return Decimal("0"), "position_limit"
    if not trade.market_open:
        return Decimal("0"), "market_closed"
    if not trade.spread_ok:
        return Decimal("0"), "spread_too_wide"
    if trade.current_equity_eur <= trade.daily_equity_start_eur * (Decimal(1) - risk.daily_loss_fraction):
        return Decimal("0"), "daily_loss_limit"
    if any(v <= 0 for v in (trade.loss_eur_per_lot_at_sl, trade.min_lot, trade.lot_step, trade.max_lot, trade.margin_eur_per_lot)):
        return Decimal("0"), "invalid_broker_spec"
    by_risk = risk.risk_budget_eur / trade.loss_eur_per_lot_at_sl
    by_margin = risk.equity_eur * risk.max_margin_fraction / trade.margin_eur_per_lot
    raw = min(by_risk, by_margin, trade.max_lot)
    steps = (raw / trade.lot_step).to_integral_value(rounding=ROUND_DOWN)
    volume = steps * trade.lot_step
    if volume < trade.min_lot:
        return Decimal("0"), "min_lot_exceeds_risk_or_margin_budget"
    return volume, "approved"
