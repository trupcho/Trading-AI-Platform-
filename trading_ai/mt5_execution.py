"""MT5 execution adapter for a FUTURE owner-authorized pilot.

No public endpoints, no broker login or money handling. Default is DRY-RUN
and the existing iPhone PWA must not invoke this module. Never expose this
adapter to the internet without independently audited authentication and TLS.

The order path is intentionally gated by explicit out-of-band owner approval
and broker-specific verification. No automated AI approval is accepted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,80}$")
SYM_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
D = lambda v: Decimal(str(v))


@dataclass(frozen=True)
class PilotPolicy:
    capital_ceiling_eur: Decimal = Decimal("100")
    risk_fraction: Decimal = Decimal("0.0025")
    daily_loss_fraction: Decimal = Decimal("0.01")
    margin_fraction: Decimal = Decimal("0.35")
    max_spread_price: Decimal = Decimal("0.5")
    max_tick_age_seconds: int = 5
    max_positions: int = 1


@dataclass(frozen=True)
class Intent:
    idempotency_key: str
    symbol: str
    direction: str  # BUY or SELL
    stop_distance: Decimal
    target_distance: Decimal
    approved_until_epoch: int
    human_approved: bool


def guard_snapshot(*, intent: Intent, policy: PilotPolicy, equity: Any,
                   daily_baseline: Any, lot: Any, step: Any, margin: Any,
                   loss_to_stop: Any, cost_buffer: Any, spread: Any,
                   min_stop_distance: Any, positions: int,
                   pending_orders: int, tick_age_seconds: Any,
                   account_mode: str, account_currency: str,
                   now: int) -> str:
    """Pure gate: returns a blocking reason or READY_FOR_ORDER_CHECK.

    READY_FOR_ORDER_CHECK is NOT an instruction to execute a trade.
    """
    if not ID_PATTERN.fullmatch(intent.idempotency_key or ""):
        return "INVALID_INTENT_ID"
    if not SYM_PATTERN.fullmatch(intent.symbol or "") or intent.direction not in ("BUY", "SELL"):
        return "INVALID_INTENT"
    if not intent.human_approved or intent.approved_until_epoch <= now or intent.approved_until_epoch > now + 300:
        return "NO_FRESH_OWNER_APPROVAL"
    if account_mode not in ("DEMO", "REAL") or account_currency != "EUR":
        return "UNSUPPORTED_ACCOUNT"
    # Pilot risk policy is a hard ceiling, never an adjustable shortcut.
    try:
        if (policy.max_positions != 1 or
            not Decimal("0") < policy.risk_fraction <= Decimal("0.0025") or
            not Decimal("0") < policy.daily_loss_fraction <= Decimal("0.01") or
            not Decimal("0") < policy.margin_fraction <= Decimal("0.35") or
            not Decimal("0") < policy.capital_ceiling_eur <= Decimal("100") or
            not Decimal("0") < policy.max_spread_price <= Decimal("0.5") or
            not 0 < policy.max_tick_age_seconds <= 5):
            return "UNSAFE_RISK_POLICY"
    except (InvalidOperation, ValueError, TypeError):
        return "UNSAFE_RISK_POLICY"
    if positions != 0 or pending_orders != 0:
        return "EXPOSURE_NOT_EMPTY"
    try:
        eq, base, volume, vol_step, marg, loss, costs, spr, min_stop, tick_age = [
            D(v) for v in (equity, daily_baseline, lot, step, margin,
                           loss_to_stop, cost_buffer, spread,
                           min_stop_distance, tick_age_seconds)
        ]
        if any(not x.is_finite() for x in (eq, base, volume, vol_step, marg,
                                           loss, costs, spr, min_stop, tick_age)):
            return "NON_FINITE_BROKER_DATA"
        sd, td = D(intent.stop_distance), D(intent.target_distance)
        if not sd.is_finite() or not td.is_finite():
            return "NON_FINITE_BROKER_DATA"
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        return "INVALID_BROKER_DATA"
    if eq <= 0 or base <= 0 or volume <= 0 or vol_step <= 0 or marg <= 0 or loss < 0 or costs <= 0 or spr <= 0:
        return "INVALID_BROKER_DATA"
    if sd <= min_stop or td <= min_stop or sd <= 0 or td <= 0:
        return "INVALID_STOP_LEVELS"
    if tick_age < 0 or tick_age > policy.max_tick_age_seconds:
        return "STALE_PRICE"
    if spr > policy.max_spread_price:
        return "SPREAD_LIMIT"
    if eq <= base * (1 - policy.daily_loss_fraction):
        return "DAILY_LOSS_LIMIT"
    capital = min(eq, policy.capital_ceiling_eur)
    if marg > capital * policy.margin_fraction:
        return "MARGIN_LIMIT"
    if loss + costs > capital * policy.risk_fraction:
        return "STOP_LOSS_RISK_LIMIT"
    return "READY_FOR_ORDER_CHECK"


class Ledger:
    """Durable no-auto-retry idempotency for all attempted broker submissions."""
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("on-disk ledger required")
        if not Path(self.path).parent.exists():
            raise ValueError("ledger parent directory missing")

    def _db(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        db.execute("PRAGMA busy_timeout=20000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS submissions ("
                   "id TEXT PRIMARY KEY, account_id TEXT NOT NULL,"
                   "status TEXT NOT NULL, detail TEXT NOT NULL, at_utc INTEGER NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS baselines ("
                   "account_id TEXT NOT NULL, day TEXT NOT NULL,"
                   "equity_eur TEXT NOT NULL, PRIMARY KEY(account_id, day))")
        return db

    def baseline(self, account_id: str, day: str, current_equity: Any) -> Decimal:
        with closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO baselines VALUES (?,?,?)",
                       (account_id, day, str(current_equity)))
            v = db.execute("SELECT equity_eur FROM baselines WHERE account_id=? AND day=?",
                           (account_id, day)).fetchone()[0]
            db.execute("COMMIT")
            return D(v)

    def reserve(self, key: str, account_id: str, now: int) -> bool:
        with closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            # Block any second pending or sent order on this account, even when
            # intent identifiers differ. Human/broker reconciliation required.
            existing = db.execute(
                "SELECT 1 FROM submissions WHERE account_id=? "
                "AND status IN ('PENDING','SENT') LIMIT 1", (account_id,)
            ).fetchone()
            if existing:
                db.execute("ROLLBACK")
                return False
            try:
                db.execute("INSERT INTO submissions VALUES (?,?,?,?,?)",
                           (key, account_id, "PENDING", "may have reached broker", now))
                db.execute("COMMIT")
                return True
            except sqlite3.IntegrityError:
                db.execute("ROLLBACK")
                return False

    def finalize(self, key: str, status: str, detail: str):
        with closing(self._db()) as db:
            db.execute("UPDATE submissions SET status=?, detail=? WHERE id=?",
                       (status, detail[:200], key))


def _price_to_tick(value: Decimal, size: Decimal, *, round_up: bool) -> float:
    if size <= 0:
        raise ValueError("invalid trade tick size")
    mode = ROUND_CEILING if round_up else ROUND_FLOOR
    return float((value / size).to_integral_value(rounding=mode) * size)


def evaluate_mt5(intent: Intent, *, mt5: Any, ledger: Ledger, policy: PilotPolicy,
                 expected_login: int, expected_server: str,
                 cost_buffer_eur: Decimal, now: int | None = None) -> dict:
    """Broker-preflight; does not call order_send and never enables real trading."""
    now = int(time.time()) if now is None else now
    try:
        account = mt5.account_info()
        if account is None:
            return {"ok": False, "reason": "NO_ACCOUNT"}
        if int(account.login) != expected_login or str(account.server) != expected_server:
            return {"ok": False, "reason": "ACCOUNT_NOT_ALLOWLISTED"}
        account_mode = ("REAL" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL
                        else "DEMO" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
                        else "UNKNOWN")
        info = mt5.symbol_info(intent.symbol)
        tick = mt5.symbol_info_tick(intent.symbol)
        if info is None or tick is None or not info.visible:
            return {"ok": False, "reason": "UNAVAILABLE_SYMBOL"}
        if getattr(info, "trade_mode", None) != mt5.SYMBOL_TRADE_MODE_FULL:
            return {"ok": False, "reason": "SYMBOL_NOT_FULLY_TRADABLE"}
        pos = mt5.positions_get()
        orders = mt5.orders_get()
        if pos is None or orders is None:
            return {"ok": False, "reason": "POSITION_OR_ORDER_QUERY_FAILED"}
        if not D(info.volume_min).is_finite() or D(info.volume_min) <= 0 or D(info.volume_min) > D(info.volume_max):
            return {"ok": False, "reason": "INVALID_VOLUME_SPEC"}
        # Conservative pilot: only minimum lot, never scale volume upward.
        if D(info.volume_min) / D(info.volume_step) != (
                D(info.volume_min) / D(info.volume_step)).to_integral_value():
            return {"ok": False, "reason": "UNSUPPORTED_VOLUME_STEP"}
        age = now - int(tick.time)
        if age < 0 or age > policy.max_tick_age_seconds:
            return {"ok": False, "reason": "STALE_PRICE"}
        bid, ask = D(tick.bid), D(tick.ask)
        if bid <= 0 or ask <= bid:
            return {"ok": False, "reason": "INVALID_QUOTE"}
        volume = D(info.volume_min)
        is_buy = intent.direction == "BUY"
        side = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        entry = ask if is_buy else bid
        tick_size = D(getattr(info, "trade_tick_size", None) or info.point)
        stop = _price_to_tick(entry - D(intent.stop_distance) if is_buy else entry + D(intent.stop_distance),
                              tick_size, round_up=not is_buy)
        target = _price_to_tick(entry + D(intent.target_distance) if is_buy else entry - D(intent.target_distance),
                                tick_size, round_up=is_buy)
        if D(stop) <= 0 or D(target) <= 0:
            return {"ok": False, "reason": "INVALID_STOP_TARGET"}
        # Broker min stop distance is measured from the current bid/ask,
        # not simply entry, so include the spread buffer.
        min_stop = D(info.trade_stops_level) * D(info.point) + (ask - bid)
        margin = mt5.order_calc_margin(side, intent.symbol, float(volume), float(entry))
        loss = mt5.order_calc_profit(side, intent.symbol, float(volume), float(entry), stop)
        if margin is None or loss is None:
            return {"ok": False, "reason": "BROKER_PROFIT_MARGIN_UNAVAILABLE"}
        baseline = ledger.baseline(str(account.login), time.strftime("%Y-%m-%d", time.gmtime(now)), account.equity)
        reason = guard_snapshot(
            intent=intent, policy=policy, equity=account.equity,
            daily_baseline=baseline, lot=volume, step=info.volume_step,
            margin=margin, loss_to_stop=max(0, -D(loss)),
            cost_buffer=cost_buffer_eur, spread=ask-bid,
            min_stop_distance=min_stop, positions=len(pos),
            pending_orders=len(orders), tick_age_seconds=age,
            account_mode=account_mode, account_currency=account.currency, now=now)
        if reason != "READY_FOR_ORDER_CHECK":
            return {"ok": False, "reason": reason}
        if is_buy and (D(stop) >= bid - D(info.trade_stops_level) * D(info.point) or
                       D(target) <= bid + D(info.trade_stops_level) * D(info.point)):
            return {"ok": False, "reason": "BROKER_PRICE_LEVELS"}
        if not is_buy and (D(stop) <= ask + D(info.trade_stops_level) * D(info.point) or
                           D(target) >= ask - D(info.trade_stops_level) * D(info.point)):
            return {"ok": False, "reason": "BROKER_PRICE_LEVELS"}
        # Only order filling modes explicitly advertised by the broker.
        filling = int(getattr(info, "filling_mode", 0))
        if filling & int(mt5.SYMBOL_FILLING_IOC):
            fill_type = mt5.ORDER_FILLING_IOC
        elif filling & int(mt5.SYMBOL_FILLING_FOK):
            fill_type = mt5.ORDER_FILLING_FOK
        else:
            return {"ok": False, "reason": "NO_VALID_FILLING_POLICY"}
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": intent.symbol,
            "volume": float(volume),
            "type": side,
            "price": float(entry),
            "sl": stop,
            "tp": target,
            "deviation": 10,  # points, not dollars; broker validation still needed
            "magic": 7126001,
            "comment": ("TradingAI-" + intent.idempotency_key)[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_type,
        }
        check = mt5.order_check(request)
        if check is None or getattr(check, "retcode", None) != 0:
            return {"ok": False, "reason": "BROKER_ORDER_CHECK_REJECTED"}
        return {"ok": True, "reason": "PREFLIGHT_ONLY", "request": request,
                "account_kind": account_mode, "account_login": int(account.login)}
    except (AttributeError, ValueError, TypeError, InvalidOperation, ZeroDivisionError):
        return {"ok": False, "reason": "INVALID_MT5_OR_POLICY_DATA"}


def submit_guarded(intent: Intent, *, mt5: Any, ledger: Ledger,
                   policy: PilotPolicy, expected_login: int, expected_server: str,
                   cost_buffer_eur: Decimal, now: int | None = None) -> dict:
    """Live orders require separate non-public owner-approved runtime setup.

    No automatic retries: unresolved results need human reconciliation in MT5.
    """
    now = int(time.time()) if now is None else now
    if os.getenv("TRADING_AI_KILL_SWITCH", "1") != "0":
        return {"sent": False, "reason": "KILL_SWITCH_ACTIVE"}
    if os.getenv("TRADING_AI_LIVE_ENABLED", "") != "YES_I_ACCEPT_LIVE_RISK":
        return {"sent": False, "reason": "LIVE_DISABLED"}
    pre = evaluate_mt5(intent, mt5=mt5, ledger=ledger, policy=policy,
                       expected_login=expected_login, expected_server=expected_server,
                       cost_buffer_eur=cost_buffer_eur, now=now)
    if not pre.get("ok") or pre.get("account_kind") != "REAL":
        return {"sent": False, "reason": pre.get("reason") if not pre.get("ok") else "REAL_ACCOUNT_REQUIRED"}
    # Reserve before submitting; process crash must never auto-retry this key.
    if not ledger.reserve(intent.idempotency_key, str(expected_login), now):
        return {"sent": False, "reason": "DUPLICATE_INTENT_REQUIRES_RECONCILIATION"}
    result_status = "UNKNOWN"
    detail = "broker result uncertain; reconcile manually"
    try:
        response = mt5.order_send(pre["request"])
        if response is not None and getattr(response, "retcode", None) == mt5.TRADE_RETCODE_DONE:
            result_status = "SENT"
            detail = "broker reported trade done; verify position and SL/TP"
            return {"sent": True, "reason": "BROKER_REPORTED_DONE"}
        result_status = "BROKER_REJECTED_OR_UNKNOWN"
        return {"sent": False, "reason": "BROKER_DID_NOT_CONFIRM_EXECUTION"}
    except Exception:
        return {"sent": False, "reason": "UNKNOWN_BROKER_SUBMISSION_OUTCOME"}
    finally:
        ledger.finalize(intent.idempotency_key, result_status, detail)
