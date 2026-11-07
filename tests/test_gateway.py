import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from trading_ai.gateway import build_server

class GatewayIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key='z'*40
        cls.srv=build_server(cls.key,'127.0.0.1',0)
        cls.base=f'http://127.0.0.1:{cls.srv.server_port}'
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(3)

    def send(self,path,body=None,authorized=True):
        hdr={'X-API-Key':self.key if authorized else 'nope'}
        data=None
        if body is not None:
            data=json.dumps(body).encode()
            hdr['Content-Type']='application/json'
        req=Request(self.base+path,headers=hdr,data=data)
        try:
            with urlopen(req, timeout=3) as r:
                return r.status, r.read().decode()
        except HTTPError as e:
            return e.code, e.read().decode()

    def test_unauthorized(self):
        code,_=self.send('/v1/status', authorized=False)
        self.assertEqual(code,401)
    def test_halt_default(self):
        code,body=self.send('/v1/mt5/policy?symbol=XAUUSD')
        self.assertEqual(code,200)
        self.assertIn('|HALT|',body)
    def test_cannot_approve_by_default(self):
        with patch.dict(os.environ, {'TRADING_AI_ALLOW_DEMO_APPROVAL':'0'}):
            code,_=self.send('/v1/demo/approve',{'symbol':'XAUUSD','mode':'BUY_ONLY'})
        self.assertEqual(code,403)
    def test_approval_expires_and_halts(self):
        with patch.dict(os.environ, {'TRADING_AI_ALLOW_DEMO_APPROVAL':'1'}):
            code,_=self.send('/v1/demo/approve',{'symbol':'NAS100','mode':'SELL_ONLY','ttl_seconds':1})
        self.assertEqual(code,200)
        code,wire=self.send('/v1/mt5/policy?symbol=NAS100')
        self.assertEqual(code,200)
        self.assertIn('|SELL_ONLY|',wire)
        p=self.srv.state.policies['NAS100']
        self.assertIn('|HALT|',p.mt5_wire(p.expires_at))
    def test_reject_live_heartbeat(self):
        code,_=self.send('/v1/mt5/heartbeat',{'symbol':'XAUUSD','balance':500,'equity':500,'positions':0,'demo':False})
        self.assertEqual(code,400)
    def test_demo_heartbeat(self):
        code,_=self.send('/v1/mt5/heartbeat',{'symbol':'XAUUSD','balance':500,'equity':498,'positions':0,'demo':True})
        self.assertEqual(code,200)
        code,status=self.send('/v1/status')
        self.assertEqual(code,200)
        self.assertEqual(json.loads(status)['heartbeats']['XAUUSD']['equity'],498)
    def test_dashboard(self):
        code,body=self.send('/')
        self.assertEqual(code,200)
        self.assertIn('TRADING AI',body)

if __name__=='__main__':
    unittest.main()
