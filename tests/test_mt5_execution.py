"""Broker simulator tests. These tests cannot place orders at a real broker."""
import os
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace as NS
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from trading_ai.mt5_execution import (
    PilotPolicy, Intent, Ledger, guard_snapshot, evaluate_mt5, submit_guarded)


class FakeMT5:
    ACCOUNT_TRADE_MODE_REAL = 2
    ACCOUNT_TRADE_MODE_DEMO = 0
    SYMBOL_TRADE_MODE_FULL = 4
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    SYMBOL_FILLING_IOC = 2
    SYMBOL_FILLING_FOK = 1
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_FOK = 0
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.account = NS(login=123456, server="TEST-EU-MT5", trade_mode=2,
                          currency="EUR", balance=100, equity=100)
        self.info = NS(visible=True, trade_mode=4, volume_min=.0001,
                       volume_step=.0001, volume_max=5, trade_stops_level=0,
                       point=.01, trade_tick_size=.01, filling_mode=2)
        self.tick = NS(bid=4000.0, ask=4000.15, time=1000)
        self.positions = ()
        self.orders = ()
        self.check = NS(retcode=0)
        self.send = NS(retcode=10009)
        self.send_count = 0
        self.sent_request = None
        self.profit = -.12
        self.margin = 12

    def account_info(self): return self.account
    def symbol_info(self, symbol): return self.info
    def symbol_info_tick(self, symbol): return self.tick
    def positions_get(self): return self.positions
    def orders_get(self): return self.orders
    def order_calc_margin(self, *args): return self.margin
    def order_calc_profit(self, *args): return self.profit
    def order_check(self, request): self.sent_request = request;return self.check
    def order_send(self, request):
        self.send_count += 1
        self.sent_request = request
        return self.send


def approved(key="pilot-2026-00000001", direction="BUY"):
    return Intent(key, "XAUUSD", direction, Decimal("5"), Decimal("8"), 1100, True)


class ExecutionTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name) / "ledger.sqlite")
        self.mt = FakeMT5()
        self.kw = dict(mt5=self.mt, ledger=self.ledger, policy=PilotPolicy(),
                       expected_login=123456, expected_server="TEST-EU-MT5",
                       cost_buffer_eur=Decimal(".03"), now=1000)

    def test_preflight_valid_is_not_submission(self):
        result = evaluate_mt5(approved(), **self.kw)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "PREFLIGHT_ONLY")
        self.assertEqual(self.mt.send_count, 0)
        self.assertGreater(result["request"]["tp"], result["request"]["price"])
        self.assertLess(result["request"]["sl"], result["request"]["price"])

    def test_kill_switch_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            r = submit_guarded(approved(), **self.kw)
        self.assertEqual(r["reason"], "KILL_SWITCH_ACTIVE")
        self.assertEqual(self.mt.send_count, 0)

    def test_live_flag_required(self):
        with patch.dict(os.environ, {"TRADING_AI_KILL_SWITCH": "0"}, clear=True):
            r = submit_guarded(approved(), **self.kw)
        self.assertEqual(r["reason"], "LIVE_DISABLED")

    def test_demo_never_executes(self):
        self.mt.account.trade_mode=0
        with patch.dict(os.environ, {"TRADING_AI_KILL_SWITCH":"0",
             "TRADING_AI_LIVE_ENABLED":"YES_I_ACCEPT_LIVE_RISK"}, clear=True):
            r=submit_guarded(approved(),**self.kw)
        self.assertFalse(r["sent"])
        self.assertEqual(r["reason"],"REAL_ACCOUNT_REQUIRED")

    def test_wrong_account_blocked(self):
        self.kw["expected_login"]=123457
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],
                         "ACCOUNT_NOT_ALLOWLISTED")

    def test_spread_blocked(self):
        self.mt.tick.ask=4001
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"], "SPREAD_LIMIT")

    def test_volume_or_margin_blocked(self):
        self.mt.margin=45
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"MARGIN_LIMIT")

    def test_loss_risk_blocked(self):
        self.mt.profit=-.3
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"STOP_LOSS_RISK_LIMIT")

    def test_stale_tick_blocked(self):
        self.mt.tick.time=980
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"STALE_PRICE")

    def test_position_query_failure_blocks(self):
        self.mt.positions=None
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],
                         "POSITION_OR_ORDER_QUERY_FAILED")

    def test_open_position_blocks(self):
        self.mt.positions=(NS(ticket=1),)
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"EXPOSURE_NOT_EMPTY")

    def test_pending_order_blocks(self):
        self.mt.orders=(NS(ticket=5),)
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"EXPOSURE_NOT_EMPTY")

    def test_owner_approval_expires(self):
        i=Intent("pilot-2026-00000001","XAUUSD","BUY",Decimal(5),Decimal(8),1000,True)
        self.assertEqual(evaluate_mt5(i,**self.kw)["reason"],"NO_FRESH_OWNER_APPROVAL")

    def test_overlong_owner_approval_blocks(self):
        i=Intent("pilot-2026-00000001","XAUUSD","BUY",Decimal(5),Decimal(8),1400,True)
        self.assertEqual(evaluate_mt5(i,**self.kw)["reason"],"NO_FRESH_OWNER_APPROVAL")

    def test_missing_owner_approval_blocks(self):
        i=Intent("pilot-2026-00000001","XAUUSD","BUY",Decimal(5),Decimal(8),1100,False)
        self.assertEqual(evaluate_mt5(i,**self.kw)["reason"],"NO_FRESH_OWNER_APPROVAL")

    def test_invalid_broker_filling_blocks(self):
        self.mt.info.filling_mode=0
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"NO_VALID_FILLING_POLICY")

    def test_broker_order_check_blocks(self):
        self.mt.check.retcode=10013
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"BROKER_ORDER_CHECK_REJECTED")

    def test_daily_loss_halt_persists_restart(self):
        self.assertTrue(evaluate_mt5(approved(),**self.kw)["ok"])
        self.mt.account.equity=98.5
        other=Ledger(Path(self.tmp.name)/"ledger.sqlite")
        self.kw["ledger"]=other
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"DAILY_LOSS_LIMIT")

    def test_no_auto_retry_after_send(self):
        env={"TRADING_AI_KILL_SWITCH":"0",
             "TRADING_AI_LIVE_ENABLED":"YES_I_ACCEPT_LIVE_RISK"}
        with patch.dict(os.environ,env,clear=True):
            first=submit_guarded(approved(),**self.kw)
            second=submit_guarded(approved(),**self.kw)
        self.assertTrue(first["sent"])
        self.assertFalse(second["sent"])
        self.assertEqual(second["reason"],"DUPLICATE_INTENT_REQUIRES_RECONCILIATION")
        self.assertEqual(self.mt.send_count,1)

    def test_distinct_concurrent_intent_blocked_until_reconciliation(self):
        env={"TRADING_AI_KILL_SWITCH":"0",
             "TRADING_AI_LIVE_ENABLED":"YES_I_ACCEPT_LIVE_RISK"}
        with patch.dict(os.environ,env,clear=True):
            first=submit_guarded(approved(key="pilot-2026-00000001"),**self.kw)
            second=submit_guarded(approved(key="pilot-2026-00000002"),**self.kw)
        self.assertTrue(first["sent"])
        self.assertFalse(second["sent"])
        self.assertEqual(second["reason"],"DUPLICATE_INTENT_REQUIRES_RECONCILIATION")
        self.assertEqual(self.mt.send_count,1)

    def test_custom_policy_cannot_exceed_pilot_risk_ceiling(self):
        self.kw["policy"]=PilotPolicy(risk_fraction=Decimal(".05"))
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"UNSAFE_RISK_POLICY")

    def test_custom_margin_policy_cannot_exceed_ceiling(self):
        self.kw["policy"]=PilotPolicy(margin_fraction=Decimal(".8"))
        self.assertEqual(evaluate_mt5(approved(),**self.kw)["reason"],"UNSAFE_RISK_POLICY")

    def test_non_finite_stop_rejected(self):
        i=Intent("pilot-2026-00000001","XAUUSD","BUY",Decimal("NaN"),Decimal(8),1100,True)
        self.assertEqual(evaluate_mt5(i,**self.kw)["reason"],"NON_FINITE_BROKER_DATA")

    def test_sell_stop_and_target(self):
        r=evaluate_mt5(approved(direction="SELL"),**self.kw)
        self.assertTrue(r["ok"])
        self.assertGreater(r["request"]["sl"],r["request"]["price"])
        self.assertLess(r["request"]["tp"],r["request"]["price"])

    def test_unknown_broker_result_is_not_retried(self):
        self.mt.send=None
        env={"TRADING_AI_KILL_SWITCH":"0",
             "TRADING_AI_LIVE_ENABLED":"YES_I_ACCEPT_LIVE_RISK"}
        with patch.dict(os.environ,env,clear=True):
            first=submit_guarded(approved(),**self.kw)
            second=submit_guarded(approved(),**self.kw)
        self.assertFalse(first["sent"])
        self.assertEqual(first["reason"],"BROKER_DID_NOT_CONFIRM_EXECUTION")
        self.assertEqual(second["reason"],"DUPLICATE_INTENT_REQUIRES_RECONCILIATION")
        self.assertEqual(self.mt.send_count,1)


if __name__=="__main__":
    import unittest
    unittest.main()
