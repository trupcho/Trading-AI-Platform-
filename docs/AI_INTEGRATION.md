# TradingAgents integration contract

**Current state: research only.** Upstream version target: TradingAgents 0.7.1, pin after installation and compatibility testing. Its `TradingAgentsGraph.propagate(ticker, date)` call returns a research state and decision but is not a deterministic, latency-bounded intraday scalping signal engine. Do not parse free-form AI prose as direct order commands.

## v0.1 boundary

```
TradingAgents -> offline JSON report -> HUMAN REVIEW -> DEMO policy (max TTL 900 seconds)
                              |                      |
                              |                      v
                              |            Python 127.0.0.1:8765
                              |                      |
                              v                      v
                      NO DIRECT ORDERS      MT5 EA directional filter
                                             + broker-aware risk checks
```

Proxies are only for qualitative research:
- `XAUUSD` research -> Yahoo `GC=F` gold futures. This is not the broker's XAUUSD spot gold CFD; prices, timestamps, liquidity and roll dates can differ.
- `NAS100` research -> Yahoo `^NDX` Nasdaq-100 index. This is not a broker's leveraged NAS100 CFD and does not share its 24-hour quote or margin model.

## Proposed v0.2 AI service

- Broker-provided M1/M5 bars with timestamps and spread. Reject missing/stale/forward-filled prices.
- Calendar-based high-impact news freeze, with explicit data provider license and timezone normalization.
- Extract **structured typed** AI output, *schema validation*; discard invalid/hallucinated values.
- Normalize symbol identity to a broker mapping table (no fuzzy matching).
- Version policies and tie each to source data timestamp, model version, and explicit expiry.
- Backtest using rolling train/validation/test splits and freeze changes before out-of-sample periods.
- Compare AI-enabled strategy to EA-only benchmark; keep AI only if it yields a robust improvement after costs.
- Manual approval remains mandatory until prospective demo testing establishes safety.

## Security and risk invariants

1. AI cannot increase lot size, leverage, maximum positions, risk per trade, or stop-loss limits.
2. No broker credentials or live-trade authority in the Python AI process.
3. Only MQL5 EA, on demo accounts, executes any orders in v0.1.
4. Gateway serves localhost only and requires a random API token. Use environment variables, never GitHub source.
5. Loss limits are best-effort; gaps and slippage may exceed a planned loss.
6. If policy is malformed, gateway unreachable, or expired, EA must stop opening new positions.
