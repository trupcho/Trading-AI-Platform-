"""Send a MANUAL, bounded and demo-only approval to loopback gateway."""
import argparse
import json
import os
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--mode", choices=["HALT", "BUY_ONLY", "SELL_ONLY", "BOTH"], required=True)
    ap.add_argument("--ttl", type=int, default=300)
    args = ap.parse_args()
    key = os.getenv("TRADING_AI_GATEWAY_KEY", "")
    body = json.dumps({"symbol":args.symbol,"mode":args.mode,"ttl_seconds":args.ttl}).encode()
    req = urllib.request.Request("http://127.0.0.1:8765/v1/demo/approve", data=body,
        headers={"X-API-Key":key,"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req, timeout=4) as r:
        print(r.read().decode())

if __name__ == "__main__":
    main()
