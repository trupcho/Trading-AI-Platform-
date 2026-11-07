import unittest
from decimal import Decimal
from trading_ai.policy import DirectionPolicy, halted
from trading_ai.risk import AccountRisk, Candidate, permitted_volume
from trading_ai.gateway import build_server

class PolicyTests(unittest.TestCase):
    def test_halt_by_default(self):
        self.assertIn('|HALT|', halted('XAUUSD').mt5_wire())
    def test_expiry_fail_closed(self):
        p=DirectionPolicy('XAUUSD','BUY_ONLY',10,20)
        self.assertIn('|HALT|',p.mt5_wire(21))
    def test_reject_large_ttl(self):
        with self.assertRaises(ValueError):
            DirectionPolicy.issued('XAUUSD','BUY_ONLY',1000)
    def test_reject_bad_symbol(self):
        with self.assertRaises(ValueError):
            DirectionPolicy.issued('../bad','BOTH')
    def test_strict_demo_only_server(self):
        with self.assertRaises(ValueError):
            build_server('a'*40,'0.0.0.0',0)

class RiskTests(unittest.TestCase):
    def setUp(self):
        self.risk = AccountRisk()
        self.c=Candidate(loss_eur_per_lot_at_sl=Decimal('100'),min_lot=Decimal('0.01'),lot_step=Decimal('0.01'),max_lot=Decimal('100'),margin_eur_per_lot=Decimal('1000'),current_positions=0,daily_equity_start_eur=Decimal('500'),current_equity_eur=Decimal('500'),spread_ok=True,market_open=True)
    def test_budget(self):
        self.assertEqual(self.risk.risk_budget_eur,Decimal('1.25'))
    def test_volume(self):
        self.assertEqual(permitted_volume(self.risk,self.c),(Decimal('0.01'),'approved'))
    def test_minlot_blocks(self):
        from dataclasses import replace
        c=replace(self.c,loss_eur_per_lot_at_sl=Decimal('250'))
        self.assertEqual(permitted_volume(self.risk,c)[1],'min_lot_exceeds_risk_or_margin_budget')
    def test_daily_stop(self):
        from dataclasses import replace
        c=replace(self.c,current_equity_eur=Decimal('495'))
        self.assertEqual(permitted_volume(self.risk,c)[1],'daily_loss_limit')
    def test_existing_position_blocks(self):
        from dataclasses import replace
        c=replace(self.c,current_positions=1)
        self.assertEqual(permitted_volume(self.risk,c)[1],'position_limit')
    def test_spread_blocks(self):
        from dataclasses import replace
        c=replace(self.c,spread_ok=False)
        self.assertEqual(permitted_volume(self.risk,c)[1],'spread_too_wide')

if __name__=='__main__':
    unittest.main()
