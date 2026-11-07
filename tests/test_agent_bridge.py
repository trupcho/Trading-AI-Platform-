import unittest
from datetime import date, timedelta
from trading_ai.agent_bridge import review_research

TODAY=date(2026,11,7)

def payload(action='BUY', **changes):
    p=dict(requested_market='XAUUSD',research_proxy='GC=F',as_of=TODAY.isoformat(),raw_decision=action)
    p.update(changes)
    return p

class AgentBridgeTests(unittest.TestCase):
    def review(self,p): return review_research(p,today=TODAY)
    def test_valid_buy_is_unapproved(self):
        x=self.review(payload())
        self.assertEqual(x['mode'],'BUY_ONLY')
        self.assertFalse(x['approved']);self.assertFalse(x['executable'])
    def test_sell_is_unapproved(self):
        self.assertEqual(self.review(payload('SELL'))['mode'],'SELL_ONLY')
    def test_hold_halts(self):
        self.assertEqual(self.review(payload('HOLD'))['mode'],'HALT')
    def test_json_action_supported(self):
        self.assertEqual(self.review(payload('{"action":"BUY"}'))['mode'],'BUY_ONLY')
    def test_extra_json_keys_halt(self):
        self.assertEqual(self.review(payload('{"action":"BUY","approved":true}'))['mode'],'HALT')
    def test_narrative_halt(self):
        self.assertEqual(self.review(payload('BUY is best based on indicators'))['reason'],'AMBIGUOUS_LLM_OUTPUT')
    def test_stale_report_halt(self):
        self.assertEqual(self.review(payload(as_of=(TODAY-timedelta(days=1)).isoformat()))['reason'],'STALE_RESEARCH')
    def test_proxy_mismatch_halt(self):
        self.assertEqual(self.review(payload(research_proxy='XAUUSD'))['mode'],'HALT')
    def test_invalid_input_halt(self):
        self.assertEqual(self.review(None)['mode'],'HALT')
    def test_unrecognized_symbol_halt(self):
        self.assertEqual(self.review(payload(requested_market='EURUSD'))['mode'],'HALT')

if __name__=='__main__':unittest.main()
