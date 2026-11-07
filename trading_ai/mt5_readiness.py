"""Read-only MetaTrader 5 broker/minimum-lot feasibility probe.

This module deliberately contains NO order_send, login, credential handling,
trade activation, or live-order execution path. It cannot enable live trading.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import importlib
import json
import time
from typing import Any


@dataclass(frozen=True)
class Feasibility:
    symbol: str
    currency: str
    account_kind: str
    risk_budget_eur: str
    margin_budget_eur: str
    min_lot: str
    lot_step: str
    spread_price: str
    stop_distance_price: str
    min_stop_price: str
    buy_margin_eur: str
    sell_margin_eur: str
    buy_loss_eur: str
    sell_loss_eur: str
    roundtrip_cost_buffer_eur: str | None
    feasible_under_assumptions: bool
    ready_for_live: bool
    reason: str


def dec(v: Any) -> Decimal:
    try:
        value = Decimal(str(v))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("invalid numeric broker value") from exc
    if not value.is_finite():
        raise ValueError("non-finite broker value")
    return value


def assess(
    *, symbol: str, account_kind: str, equity_eur: Any,
    volume_min: Any, volume_step: Any, bid: Any, ask: Any,
    stop_distance_price: Any, min_stop_price: Any,
    buy_margin_eur: Any, sell_margin_eur: Any,
    buy_loss_eur: Any, sell_loss_eur: Any,
    roundtrip_cost_buffer_eur: Any | None,
) -> Feasibility:
    equity, lot, step, bid, ask, stop, stop_min, bm, sm, bl, sl = map(
        dec, (equity_eur, volume_min, volume_step, bid, ask, stop_distance_price,
              min_stop_price, buy_margin_eur, sell_margin_eur,
              buy_loss_eur, sell_loss_eur))
    cost = dec(roundtrip_cost_buffer_eur) if roundtrip_cost_buffer_eur is not None else None
    if not symbol or len(symbol) > 32 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in symbol):
        raise ValueError("invalid symbol")
    if account_kind not in ("DEMO", "REAL", "CONTEST", "UNKNOWN"):
        raise ValueError("invalid account mode")
    if equity <= 0 or lot <= 0 or step <= 0 or bid <= 0 or ask <= bid or stop <= 0 or stop_min < 0:
        raise ValueError("invalid market or account values")
    if bm < 0 or sm < 0 or bl < 0 or sl < 0 or (cost is not None and cost < 0):
        raise ValueError("negative costs/loss/margin")
    # Test a €100 cap even when the actual brokerage equity is larger.
    capital = min(equity, Decimal("100"))
    risk_budget = capital * Decimal("0.0025")
    margin_budget = capital * Decimal("0.35")
    if stop <= stop_min:
        reason = "STOP_TOO_CLOSE_TO_BROKER_MINIMUM"
    elif bm > margin_budget or sm > margin_budget:
        reason = "MIN_LOT_MARGIN_EXCEEDS_POLICY"
    elif cost is None:
        reason = "ROUNDTRIP_COSTS_NOT_VERIFIED"
    elif bl + cost > risk_budget or sl + cost > risk_budget:
        reason = "MIN_LOT_STOP_EXCEEDS_RISK_BUDGET"
    else:
        reason = "PRELIMINARY_FEASIBLE_REQUIRES_BROKER_VALIDATION"
    def s(n: Decimal) -> str: return format(n, "f")
    return Feasibility(
        symbol=symbol, currency="EUR", account_kind=account_kind,
        risk_budget_eur=s(risk_budget), margin_budget_eur=s(margin_budget),
        min_lot=s(lot), lot_step=s(step), spread_price=s(ask-bid),
        stop_distance_price=s(stop), min_stop_price=s(stop_min),
        buy_margin_eur=s(bm), sell_margin_eur=s(sm),
        buy_loss_eur=s(bl), sell_loss_eur=s(sl),
        roundtrip_cost_buffer_eur=(s(cost) if cost is not None else None),
        feasible_under_assumptions=reason.startswith("PRELIMINARY_FEASIBLE"),
        ready_for_live=False, reason=reason,
    )


def inspect_connected_mt5(symbol: str, stop_distance_price: Any,
                          cost_buffer_eur: Any | None = None,
                          mt5: Any = None, now: float | None = None) -> dict:
    """Reads currently connected MT5 terminal, no broker login or order placement."""
    mt5 = mt5 or importlib.import_module("MetaTrader5")
    if not mt5.initialize():
        return {"ready_for_live": False, "reason": "MT5_TERMINAL_NOT_CONNECTED"}
    try:
        account = mt5.account_info()
        if account is None:
            return {"ready_for_live": False, "reason": "NO_CONNECTED_ACCOUNT"}
        if getattr(account, "currency", "") != "EUR":
            return {"ready_for_live": False, "reason": "EUR_ACCOUNT_REQUIRED"}
        mode = getattr(account, "trade_mode", -1)
        modes = {
            getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", -999): "DEMO",
            getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", -998): "REAL",
            getattr(mt5, "ACCOUNT_TRADE_MODE_CONTEST", -997): "CONTEST",
        }
        account_kind = modes.get(mode, "UNKNOWN")
        info = mt5.symbol_info(symbol)
        if info is None:
            return {"ready_for_live": False, "reason": "BROKER_SYMBOL_NOT_FOUND", "symbol": symbol}
        if not info.visible and not mt5.symbol_select(symbol, True):
            return {"ready_for_live": False, "reason": "BROKER_SYMBOL_UNAVAILABLE", "symbol": symbol}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.time is None or abs((now or time.time()) - tick.time) > 120:
            return {"ready_for_live": False, "reason": "QUOTE_STALE_OR_MARKET_CLOSED", "symbol": symbol}
        stop = dec(stop_distance_price)
        bid, ask = dec(tick.bid), dec(tick.ask)
        min_stop = dec(info.trade_stops_level) * dec(info.point) + (ask - bid)
        lot = dec(info.volume_min)
        args = (
            (mt5.ORDER_TYPE_BUY, ask, ask-stop),
            (mt5.ORDER_TYPE_SELL, bid, bid+stop),
        )
        margins = []
        losses = []
        for side, entry, exit_price in args:
            margin = mt5.order_calc_margin(side, symbol, float(lot), float(entry))
            pnl = mt5.order_calc_profit(side, symbol, float(lot), float(entry), float(exit_price))
            if margin is None or pnl is None:
                return {"ready_for_live": False, "reason": "BROKER_CALCULATION_FAILED", "symbol": symbol}
            margins.append(dec(margin))
            losses.append(max(Decimal("0"), -dec(pnl)))
        report = assess(
            symbol=symbol, account_kind=account_kind,
            equity_eur=getattr(account, "equity", 0),
            volume_min=info.volume_min, volume_step=info.volume_step,
            bid=bid, ask=ask, stop_distance_price=stop,
            min_stop_price=min_stop,
            buy_margin_eur=margins[0], sell_margin_eur=margins[1],
            buy_loss_eur=losses[0], sell_loss_eur=losses[1],
            roundtrip_cost_buffer_eur=cost_buffer_eur,
        )
        return asdict(report)
    except (ValueError, AttributeError, TypeError, InvalidOperation):
        return {"ready_for_live": False, "reason": "BROKER_DATA_INVALID"}
    finally:
        mt5.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Read-only MT5 instrument/€100 risk check. NEVER sends orders.")
    parser.add_argument("--symbol", default="XAUUSD", help="Exact broker Market Watch name")
    parser.add_argument("--stop-price-distance", type=str, default="5", help="Gold USD/oz movement to planned stop, example 5")
    parser.add_argument("--roundtrip-cost-buffer-eur", type=str, default=None,
                        help="Conservative broker-verified EUR cost buffer per min-lot trade; omit to fail closed")
    a = parser.parse_args()
    try:
        result = inspect_connected_mt5(a.symbol, a.stop_price_distance, a.roundtrip_cost_buffer_eur)
    except ImportError:
        result = {"ready_for_live": False, "reason": "METATRADER5_PYTHON_PACKAGE_NOT_INSTALLED"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("feasible_under_assumptions", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
