import unittest
from decimal import Decimal as D
from trading_ai.gold_feasibility import GoldContract, evaluate_minimum_gold_trade


class GoldFeasibilityTests(unittest.TestCase):
    def check(self, contract, stop=D('5'), equity=D('100')):
        return evaluate_minimum_gold_trade(
            equity_eur=equity, usd_per_eur=D('1.16'), gold_usd_per_oz=D('4070'),
            stop_usd_per_oz=stop, slippage_buffer_usd_per_oz=D('1'),
            contract=contract,
        )

    def test_standard_contract_cannot_fit_100_eur_margin(self):
        result = self.check(GoldContract(D('0.01'), D('100'), D('20'), D('0.5')))
        self.assertFalse(result.approved)
        self.assertEqual(result.reason, 'MIN_LOT_MARGIN_EXCEEDS_LIMIT')
        self.assertGreater(result.estimated_margin_eur, D('100'))

    def test_tenth_ounce_can_still_fail_risk(self):
        result = self.check(GoldContract(D('0.001'), D('100'), D('20'), D('0.5')))
        self.assertFalse(result.approved)
        self.assertEqual(result.reason, 'MIN_LOT_STOP_EXCEEDS_RISK_LIMIT')

    def test_smaller_minimum_volume_can_pass_only_illustratively(self):
        result = self.check(GoldContract(D('0.0001'), D('100'), D('20'), D('0.5')))
        self.assertTrue(result.approved)
        self.assertIn('MT5_VERIFICATION', result.reason)

    def test_commission_can_block_previously_viable_trade(self):
        c = GoldContract(D('0.0001'), D('100'), D('20'), D('0.5'), D('0.30'))
        result = self.check(c)
        self.assertFalse(result.approved)
        self.assertEqual(result.reason, 'MIN_LOT_STOP_EXCEEDS_RISK_LIMIT')

    def test_small_balance_has_small_risk_budget(self):
        r = self.check(GoldContract(D('0.01'), D('100'), D('20'), D('0.5')))
        self.assertEqual(r.risk_budget_eur, D('0.25'))
        self.assertEqual(r.margin_budget_eur, D('35'))

    def test_zero_usd_rate_is_invalid(self):
        c = GoldContract(D('0.01'), D('100'), D('20'), D('0.5'))
        with self.assertRaises(ValueError):
            evaluate_minimum_gold_trade(equity_eur=D('100'), usd_per_eur=D('0'),
                gold_usd_per_oz=D('4070'), stop_usd_per_oz=D('5'),
                slippage_buffer_usd_per_oz=D('1'), contract=c)

    def test_reject_overly_high_risk_limit(self):
        c = GoldContract(D('0.01'), D('100'), D('20'), D('0.5'))
        with self.assertRaises(ValueError):
            evaluate_minimum_gold_trade(equity_eur=D('100'), usd_per_eur=D('1.16'),
                gold_usd_per_oz=D('4070'), stop_usd_per_oz=D('5'),
                slippage_buffer_usd_per_oz=D('1'), contract=c, risk_pct=D('10'))


if __name__ == '__main__':
    unittest.main()
