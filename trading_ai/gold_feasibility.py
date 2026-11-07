"""Gold CFD minimum-lot feasibility check, for research / dry runs only.

Do NOT use these estimates to send orders. Actual MT5 execution must validate
OrderCalcProfit/OrderCalcMargin, broker currency conversion, symbol trading
conditions, free margin, stop-level rules, and final execution costs.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal


def D(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class GoldContract:
    min_lot: Decimal
    contract_ounces_per_lot: Decimal
    leverage: Decimal
    spread_usd_per_oz: Decimal
    round_trip_commission_eur: Decimal = Decimal("0")


@dataclass(frozen=True)
class GoldFeasibility:
    approved: bool
    reason: str
    minimum_lot: Decimal
    estimated_margin_eur: Decimal
    estimated_stop_loss_eur: Decimal
    risk_budget_eur: Decimal
    margin_budget_eur: Decimal


def evaluate_minimum_gold_trade(
    *, equity_eur: Decimal, usd_per_eur: Decimal, gold_usd_per_oz: Decimal,
    stop_usd_per_oz: Decimal, slippage_buffer_usd_per_oz: Decimal,
    contract: GoldContract, risk_pct: Decimal = Decimal("0.25"),
    margin_cap_pct: Decimal = Decimal("35"),
) -> GoldFeasibility:
    """Conservative check: minimum lot must satisfy BOTH stop-loss and margin.

    Stop loss includes estimated spread, commission, and extra slippage buffer;
    this is NOT a guaranteed worst-case loss under gaps or broker outages.
    """
    numbers = (
        equity_eur, usd_per_eur, gold_usd_per_oz, stop_usd_per_oz,
        contract.min_lot, contract.contract_ounces_per_lot, contract.leverage,
        contract.spread_usd_per_oz, contract.round_trip_commission_eur,
        slippage_buffer_usd_per_oz, risk_pct, margin_cap_pct,
    )
    if any(not n.is_finite() for n in numbers):
        raise ValueError("non-finite input")
    if any(n <= 0 for n in (
        equity_eur, usd_per_eur, gold_usd_per_oz, stop_usd_per_oz,
        contract.min_lot, contract.contract_ounces_per_lot, contract.leverage,
        risk_pct, margin_cap_pct,
    )):
        raise ValueError("invalid nonpositive input")
    if contract.spread_usd_per_oz < 0 or contract.round_trip_commission_eur < 0 or slippage_buffer_usd_per_oz < 0:
        raise ValueError("negative estimated cost")
    if risk_pct > Decimal("1") or margin_cap_pct > Decimal("35"):
        raise ValueError("exceeds conservative policy")

    ounces = contract.min_lot * contract.contract_ounces_per_lot
    margin = ounces * gold_usd_per_oz / contract.leverage / usd_per_eur
    risk = (stop_usd_per_oz + contract.spread_usd_per_oz + slippage_buffer_usd_per_oz) * ounces / usd_per_eur
    risk += contract.round_trip_commission_eur
    risk_budget = equity_eur * risk_pct / Decimal("100")
    margin_budget = equity_eur * margin_cap_pct / Decimal("100")

    if margin > margin_budget:
        reason = "MIN_LOT_MARGIN_EXCEEDS_LIMIT"
    elif risk > risk_budget:
        reason = "MIN_LOT_STOP_EXCEEDS_RISK_LIMIT"
    else:
        reason = "ILLUSTRATIVE_PASS_REQUIRES_LIVE_MT5_VERIFICATION"
    return GoldFeasibility(
        approved=reason.startswith("ILLUSTRATIVE_PASS"), reason=reason,
        minimum_lot=contract.min_lot, estimated_margin_eur=margin,
        estimated_stop_loss_eur=risk, risk_budget_eur=risk_budget,
        margin_budget_eur=margin_budget,
    )
