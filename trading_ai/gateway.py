"""Loopback-only, DEMO-only policy gateway. No broker credentials or order routes.

No external-facing app/API is included in v0.1. This service deliberately binds
only to 127.0.0.1 and enforces an API key for both GET and POST calls.
"""
from __future__ import annotations
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse
from .policy import DirectionPolicy, SYMBOL, halted

WEB_DIR = Path(__file__).resolve().parent

class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.policies: dict[str, DirectionPolicy] = {}
        self.heartbeats: dict[str, dict] = {}


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "TradingAIDemo/0.1"

    def log_message(self, fmt, *args):
        pass

    def _json(self, status: int, obj: dict):
        data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, status: int, content: str, mime="text/plain; charset=utf-8"):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        provided = self.headers.get("X-API-Key", "")
        return bool(provided and hmac.compare_digest(provided, self.server.api_key))

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 8192:
            raise ValueError("invalid body size")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("expected JSON object")
        return value

    def do_GET(self):
        if not self._authorized():
            return self._json(401, {"error":"unauthorized"})
        parsed = urlparse(self.path)
        if parsed.path == "/v1/mt5/policy":
            symbol = parse_qs(parsed.query).get("symbol", [""])[0]
            if not SYMBOL.fullmatch(symbol):
                return self._json(400, {"error":"invalid_symbol"})
            with self.server.state.lock:
                policy = self.server.state.policies.get(symbol, halted(symbol))
            return self._text(200, policy.mt5_wire())
        if parsed.path == "/v1/status":
            with self.server.state.lock:
                policies = {s: {"mode": (p.mode if p.active() else "HALT"), "expires_at": p.expires_at} for s,p in self.server.state.policies.items()}
                beats = dict(self.server.state.heartbeats)
            return self._json(200, {"version":"0.1.0", "mode":"DEMO_ONLY", "policies":policies, "heartbeats": beats, "time_utc": int(time.time())})
        if parsed.path == "/":
            return self._text(200, (WEB_DIR / "dashboard.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        return self._json(404, {"error":"not_found"})

    def do_POST(self):
        if not self._authorized():
            return self._json(401, {"error":"unauthorized"})
        try:
            data = self._body()
            if self.path == "/v1/demo/approve":
                if os.getenv("TRADING_AI_ALLOW_DEMO_APPROVAL", "0") != "1":
                    return self._json(403, {"error":"demo_approval_disabled"})
                policy = DirectionPolicy.issued(str(data["symbol"]), str(data["mode"]), int(data.get("ttl_seconds", 300)))
                # approval is intentionally manual. AI research is never auto-wired to this endpoint.
                with self.server.state.lock:
                    self.server.state.policies[policy.symbol] = policy
                return self._json(200, {"ok":True, "symbol":policy.symbol, "mode":policy.mode, "expires_at":policy.expires_at})
            if self.path == "/v1/mt5/heartbeat":
                if data.get("demo") is not True:
                    raise ValueError("demo heartbeat required")
                symbol = str(data["symbol"])
                if not SYMBOL.fullmatch(symbol):
                    raise ValueError("invalid symbol")
                balance = float(data["balance"])
                equity = float(data["equity"])
                positions = int(data["positions"])
                if not (0 <= balance <= 1e12 and 0 <= equity <= 1e12 and 0 <= positions <= 10000):
                    raise ValueError("invalid heartbeat values")
                with self.server.state.lock:
                    self.server.state.heartbeats[symbol] = {"balance":balance,"equity":equity,"positions":positions,"received_at":int(time.time())}
                return self._json(200, {"ok":True})
            return self._json(404, {"error":"not_found"})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, OverflowError):
            return self._json(400, {"error":"invalid_request"})


def build_server(api_key: str, host="127.0.0.1", port=8765):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("v0.1 refuses non-loopback binding")
    if len(api_key) < 24 or api_key == "CHANGE_ME_TO_A_RANDOM_SECRET":
        raise ValueError("set TRADING_AI_GATEWAY_KEY to a randomly generated secret of >=24 characters")
    server = ThreadingHTTPServer((host, port), GatewayHandler)
    server.state = State()
    server.api_key = api_key
    return server


def main():
    key = os.getenv("TRADING_AI_GATEWAY_KEY", "")
    host = os.getenv("TRADING_AI_HOST", "127.0.0.1")
    port = int(os.getenv("TRADING_AI_PORT", "8765"))
    server = build_server(key, host, port)
    print(f"Trading AI Demo gateway listening on http://{host}:{port} (DEMO ONLY)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
