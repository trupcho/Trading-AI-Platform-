# Trading AI v0.6 — REAL MONEY RELEASE CHECKLIST

**Status: ENGINE SOURCE ONLY — NOT LIVE-READY.** User authorized a future pilot of up to €100 and accepts full possible loss. This authorization does not mean a broker connection exists or that any trading permission should be enabled immediately.

## What exists

- The iPhone GitHub Pages PWA runs an independent UI and synthetic local Paper Lab.
- TradingAgents code can run financial research, and \`agent_bridge\` parses its output into **unapproved** BUY/SELL/HOLD proposals. It is not a verified tick-driven scalping model.
- A separate read-only MT5 contract-size probe is available in \`trading_ai.mt5_readiness\`.
- The new \`trading_ai.mt5_execution\` adapter contains broker preflight and a gated order-send call. In all normal installations it cannot send real orders. It is intentionally **not exposed** to the PWA, internet or user API.

## Pilot limits (MAXIMUMS, not guarantees)

- Starting-risk allocation: €100; never use more than €100 as the risk-cap calculation, even with higher equity.
- Planned loss at stop, including conservative broker-verified cost buffer: ≤0.25% (€0.25 at €100).
- Daily equity drawdown trigger: 1% relative to persistent first-observed UTC-day equity.
- Per-trade margin cap: 35% of capped equity.
- New orders: max one position, no open pending orders; no martingale, grid or averaging down.
- Stale tick, unknown broker contract terms, unverified spread/commission/slippage costs, old owner approval, broker-spec errors, unsupported fill modes: block.
- "Kill switch" defaults to active; "live enabled" defaults to off; all real account details must be on a private owner-controlled server.
- A ledger reserves the submission ID before the call, blocks any unreconciled order even under a different ID, and intentionally refuses automatic retries. This conservative v0.6 design **does not yet support continuous unattended repeated live trades**. Verification/reconciliation automation needs implementation and audit.
- Stop Loss orders, equity checks and broker order checks cannot guarantee worst-case loss during gaps, outages or rejected orders.

## Non-negotiable production blockers

| Gate | State | Acceptance evidence |
|---|---|---|
| EU-licensed broker application, KYC, suitability | User action pending | Broker confirms approved account |
| Specific broker's gold min lot, margin, spreads and fees | Not measured | Read-only MT5 audit against that account |
| Gold position within €100 and €0.25 risk cap | Unknown | Preflight permits the min lot under realistic price/fee assumptions |
| Compile, review and broker-specific MT5 execution | Not verified | Real terminal logs and reproducible checks |
| AI signal model tied to genuine broker quotes | Not implemented | Broker-aligned time series and source freshness checks |
| Backtest with actual spreads/slippage/out-of-sample | Not performed | Full metrics/report; no look-ahead bias |
| Demo execution, failover and stop testing | Not performed | Evidence of live-market demo ticks and controlled order exits |
| Authenticated single-owner remote backend with TLS/MFA | Not implemented | Penetration/security tests and protected deployment |
| Isolated long-running Windows host / MT5 terminal | Not provisioned | Owner-controlled Windows VPS with monitoring |
| Reconciliation of fills/SL/TP and repeat operations | Not implemented | Robust restart/race/failover tests |
| Broker API login / funding and withdrawals | Not integrated | Only through broker; NEVER through GitHub Pages |
| Real-money controlled release | BLOCKED | All gates passed and account owner explicitly activates live pilot |

## Operational topology

\`\`\`
iPhone PWA  -- HTTPS -->  authenticated remote API (NOT YET IMPLEMENTED)
                                  |
                             encrypted backend
                                  |
                          Windows VPS / local MT5
                                  |
                         signed signal controls
                                  |
                           MT5 execution adapter
                                  |
                            licensed broker
\`\`\`

GitHub Pages is a static website. It **cannot** safely hold broker passwords, run Windows MT5, or hold deposited money. Vercel serverless functions alone do not provide a persistent Windows MT5 terminal. There must be a long-running machine under the owner's control, and the remote API requires an identity, TLS, audit logs, rate limits, secure storage, revocation and emergency-stop design.

## Concrete broker option

OANDA TMS EU supports MT5 and application for EU residents. It has no general opening deposit minimum, but **the actual GOLD minimum volume at the specific EU account is not yet confirmed**. Do not infer EU contract settings from the UK entity's 0.001-lot gold listing. The correct check is against the approved account's MT5 \`symbol_info\`, \`order_calc_margin\` and \`order_calc_profit\`.

Reference:
- https://help.oanda.com/eu/en/faqs/mt5-user-guide-eu.htm
- https://help.oanda.com/eu/en/faqs/open-live-account-eu.htm
- https://www.mql5.com/en/docs/python_metatrader5

## Next integration implementation priorities

1. Confirm one eligible regulated MT5 broker, instrument names and account settlement currency.
2. Add single-owner authenticated API, private secrets deployment, MFA, event and fill accounting.
3. Replace proxy-only TradingAgents research with broker-quote-backed strategy signals, independent strategy/risk controller and deterministic low-latency executor; AI never receives unrestricted order/withdrawal rights.
4. Add automatic, audited fill reconciliation and broker-side hard stops; verify concurrent and restart behavior.
5. Test in Strategy Tester, then same-broker demo forward conditions, including negative tests and net costs.
6. Only after evidence: offer owner-controlled live switch and broker-funded €100 pilot.

**There is no evidence of a profitable strategy, no live account and no broker connection in this repository at present. Do not fund a broker account solely because the PWA interface looks ready.**
