"""Deterministic tests for the READ-ONLY MT5 live feasibility probe."""
import unittest
from types import SimpleNamespace
from trading_ai.mt5_readiness import assess, inspect_connected_mt5


class AssessTests(unittest.TestCase):
    def valid(self, **kwargs):
        args = dict(symbol="XAUUSD", account_kind="DEMO", equity_eur="100",
                    volume_min="0.001", volume_step="0.001", bid="4000", ask="4000.3",
                    stop_distance_price="5", min_stop_price="0.5",
                    buy_margin_eur="30", sell_margin_eur="31",
                    buy_loss_eur="0.18", sell_loss_eur="0.19",
                    roundtrip_cost_buffer_eur="0.03")
        args.update(kwargs)
        return assess(**args)

    def test_feasible_is_still_never_live_ready(self):
        a = self.valid()
        self.assertTrue(a.feasible_under_assumptions)
        self.assertFalse(a.ready_for_live)
        self.assertEqual(a.risk_budget_eur, "0.2500")
        self.assertEqual(a.margin_budget_eur, "35.00")

    def test_no_cost_information_fails_closed(self):
        self.assertEqual(self.valid(roundtrip_cost_buffer_eur=None).reason, "ROUNDTRIP_COSTS_NOT_VERIFIED")

    def test_minimum_margin_blocked(self):
        self.assertEqual(self.valid(buy_margin_eur="36").reason, "MIN_LOT_MARGIN_EXCEEDS_POLICY")

    def test_minimum_loss_blocked(self):
        self.assertEqual(self.valid(buy_loss_eur="0.24").reason, "MIN_LOT_STOP_EXCEEDS_RISK_BUDGET")

    def test_stop_too_close(self):
        self.assertEqual(self.valid(stop_distance_price="0.5").reason, "STOP_TOO_CLOSE_TO_BROKER_MINIMUM")

    def test_capital_cannot_exceed_100(self):
        self.assertEqual(self.valid(equity_eur="100000").risk_budget_eur, "0.2500")

    def test_small_equity_reduces_budget(self):
        self.assertEqual(self.valid(equity_eur="50").risk_budget_eur, "0.1250")

    def test_nan_rejected(self):
        with self.assertRaises(ValueError): self.valid(equity_eur="NaN")

    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError): self.valid(roundtrip_cost_buffer_eur="-1")


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO=0
    ACCOUNT_TRADE_MODE_REAL=2
    ACCOUNT_TRADE_MODE_CONTEST=1
    ORDER_TYPE_BUY=0
    ORDER_TYPE_SELL=1
    def __init__(self):
        self.shutdown_count=0
        self.info=SimpleNamespace(volume_min=.001,volume_step=.001,trade_stops_level=0,point=.01,visible=True)
        self.account=SimpleNamespace(currency="EUR",equity=100,trade_mode=0)
        self.tick=SimpleNamespace(time=1000,bid=4000.,ask=4000.30)
        self.orders_sent=0
    def initialize(self): return True
    def account_info(self): return self.account
    def symbol_info(self,symbol): return self.info
    def symbol_select(self,symbol,state): return True
    def symbol_info_tick(self,symbol): return self.tick
    def order_calc_margin(self,side,symbol,lot,entry): return 32
    def order_calc_profit(self,side,symbol,lot,entry,exit): return -.18
    def order_send(self,*args): self.orders_sent+=1;raise AssertionError("must never trade")
    def shutdown(self): self.shutdown_count+=1

class ProbeTests(unittest.TestCase):
    def test_read_only_never_sends_order(self):
        m=FakeMT5();r=inspect_connected_mt5("XAUUSD", "5", ".03",mt5=m,now=1000)
        self.assertTrue(r["feasible_under_assumptions"])
        self.assertFalse(r["ready_for_live"])
        self.assertEqual(m.orders_sent,0)
        self.assertEqual(m.shutdown_count,1)
        self.assertNotIn("login",r)

    def test_stale_market_fails(self):
        m=FakeMT5();r=inspect_connected_mt5("XAUUSD", "5", ".03",mt5=m,now=3000)
        self.assertEqual(r["reason"],"QUOTE_STALE_OR_MARKET_CLOSED")
        self.assertEqual(m.orders_sent,0)

    def test_eur_account_required(self):
        m=FakeMT5();m.account.currency="USD"
        r=inspect_connected_mt5("XAUUSD","5", ".03",mt5=m,now=1000)
        self.assertEqual(r["reason"],"EUR_ACCOUNT_REQUIRED")
        self.assertEqual(m.shutdown_count,1)

    def test_real_account_still_read_only(self):
        m=FakeMT5();m.account.trade_mode=2
        r=inspect_connected_mt5("XAUUSD","5", ".03",mt5=m,now=1000)
        self.assertEqual(r["account_kind"],"REAL")
        self.assertFalse(r["ready_for_live"])

    def test_failed_broker_calc(self):
        m=FakeMT5();m.order_calc_margin=lambda *a: None
        r=inspect_connected_mt5("XAUUSD","5", ".03",mt5=m,now=1000)
        self.assertEqual(r["reason"],"BROKER_CALCULATION_FAILED")

if __name__ == "__main__": unittest.main()
