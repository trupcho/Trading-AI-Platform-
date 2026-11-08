# Trading AI Platform — Gold-first v0.2 development branch (DEMO ONLY)

**Status:** starter code; Python safety tests runnable; MT5 EA is SOURCE ONLY / NOT COMPILE-VERIFIED. No real-money trading, no unbounded auto-execution, no guaranteed profits.

## Gold-first development additions (not a production release)

- A responsive gold-first mobile web monitor served by the loopback Gateway (`/`). It shows only actual Demo heartbeats; no fake profitability. The broker onboarding/deposit links lead to the broker website, not a payment form.
- A pure Python minimum-lot gold feasibility check (`trading_ai.gold_feasibility`) and regression tests. Assumptions are illustrative only; actual live trading requires MT5 broker-aware checks.
- `docs/GOLD_LIVE_READINESS.md` records the acceptance gates for a possible €100 live pilot. **Do not deposit based on the prototype.**

## What this release actually does

- **MT5 EA (MQL5)**: M1 EMA9/EMA21 crossover prototype with ATR stops, order sizing through MT5 `OrderCalcProfit()`/`OrderCalcMargin()`, maximum one total open position, daily equity-loss circuit breaker, spread filter, strict EUR/demo-only account guard, default orders OFF.
- **Loopback gateway (Python standard library)**: token-protected short-lived directional policy (`HALT`, `BUY_ONLY`, `SELL_ONLY`, `BOTH`), authenticated EA heartbeat, simple local status page. Default `HALT` and no demo signal approvals until explicitly enabled.
- **TradingAgents experiment**: optional `trading_ai.research` adapter invokes upstream `TradingAgentsGraph.propagate()` to save an *offline research report*. Its output cannot place orders or approve policies. GC=F and ^NDX are NOT executable XAUUSD/NAS100 prices.
- **Unit tests**: risk sizing, daily stop, stale policy, symbol validation, loopback restriction.
- **GitHub CI**: runs Python tests on each push/PR.

## IMPORTANT exclusions / not yet built

- No broker account, real funded balance, or external broker access.
- No remote iPhone/desktop native app yet; only a local web monitor.
- No automatic AI-to-policy promotion; v0.1 requires *manual approval*.
- No latency-optimized order routing, production tick database, historical data vendor, verified P&L or validated profitability.
- No historical multi-year broker backtesting completed; MQL5 is not compiled/verified in this environment.
- No production secrets, public internet binding, multi-user auth, websocket streaming or remote server deployment.
- XAUUSD and NAS100 are not universally the exact symbol names at brokers; choose each from Market Watch.

## Start the gateway on the same Windows host as MT5 (Python 3.11+)

PowerShell:

```powershell
cd Trading-AI-Platform-v0.1
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:TRADING_AI_GATEWAY_KEY = (py -c "import secrets; print(secrets.token_urlsafe(32))")
$env:TRADING_AI_ALLOW_DEMO_APPROVAL = '0'
py -m trading_ai.gateway
```

Open http://127.0.0.1:8765 in browser. Supply the token from your shell, which you must also paste into EA input `InpGatewayKey` in MT5. The API and dashboard bind only to loopback, not the internet.

Run safety tests:

```powershell
py -m unittest discover -s tests -v
```

To enable an explicitly authorized **manual demo directional policy** (not an order), stop gateway, set `TRADING_AI_ALLOW_DEMO_APPROVAL=1`, and restart. In a second PowerShell tab set **the same key** and call:

```powershell
py -m trading_ai.demo_cli --symbol XAUUSD --mode BUY_ONLY --ttl 300
```

Policy expires after at most 900 seconds, then EA returns to HALT. No live trading endpoint is implemented.

## MT5 demo setup

1. Open a free **Admirals Trade.MT5 Demo** account with EUR currency and **€500 virtual** starting balance, if this selectable. Confirm instrument availability and suitability in the selected EU entity; availability and server data can vary.
2. Install Windows MetaTrader 5, log into Demo, and enable `XAUUSD` or broker's exact symbol in Market Watch. Open **M1 chart**.
3. In MT5: File -> Open Data Folder -> `MQL5/Experts`; copy `mt5/Experts/TradingAI_DemoScalper.mq5` there. Open it in MetaEditor and **compile/test**. Do not deploy if any compiler errors remain.
4. In MT5 Strategy Tester use **Every tick based on real ticks** when good historical data exists; choose initial deposit **€500**, EUR, realistic leverage/fees. For tester-only offline research set `InpTesterPolicy=TAI_BOTH`, set an empirically determined `InpMaxSpreadPoints`, then explicitly set `InpEnableDemoOrders=true` **in the tester only**.
5. For forward Demo, whitelist `http://127.0.0.1:8765` under Tools -> Options -> Expert Advisors -> Allowed WebRequest URLs. Run Python gateway on the same Windows machine. Configure a token in EA. Keep `InpEnableDemoOrders=false` until compile, all risk tests and log checks pass. When enabling demo-only orders, TradingAI refuses real accounts by runtime check.
6. First simulate a **daily-loss halt**, large spread, expired policy, disconnected gateway, minimum-lot rejection, server restart, no market data, and switching to a live account. All must fail closed.
7. **Do not simply increase leverage or lot size** to make €500 XAUUSD trade. A zero-trade result under strict risk sizing is an expected valid result.

## Optional TradingAgents experiment (offline)

See `docs/AI_INTEGRATION.md`. The upstream framework has its own provider dependencies and API charges, and default config may require model API keys.

```powershell
py -m trading_ai.research --market XAUUSD --date 2026-11-06
```

This requires separate installation of TradingAgents. Upstream financial data cannot be substituted for precise broker CFD quotes. This operation **only writes a research JSON** under `research_reports/`.

## GitHub

Create a **private** GitHub repository `Trading-AI-Platform`. Extract ZIP; `git init`, `git add .`, `git commit -m "Initial demo-only Trading AI MVP"`, add your repository remote and push. The connector used in this session did not expose a create-repository action, so this release is delivered as an importable ZIP rather than claimed to be online.

Do not ever commit `.env`, passwords, TradingAgents provider keys, broker login, or actual MT5 account details.

## Evidence and limitations

- TradingAgents official repo: https://github.com/TauricResearch/TradingAgents
- MQL5 trade robot docs: https://www.metatrader5.com/en/terminal/help/algotrading
- MT5 Strategy Tester: https://www.metatrader5.com/en/terminal/help/algotrading/testing
- MT5 WebRequest whitelist: https://www.metatrader5.com/en/terminal/help/startworking/settings
- Admirals Demo: https://admiralmarkets.com/bg/start-trading/forex-demo

**Disclaimer:** Research/prototype only. CFDs are leveraged and highly risky. Risk protections are best-effort, not guaranteed loss caps under price gaps/outages.


## v0.5 — broker and TradingAgents readiness (read-only; no live orders)

The user has accepted that a future €100 pilot can lose its full capital. That **does not** turn on live trading. The current product has no live brokerage connection or profitable-strategy validation. Two separate diagnostic commands are now provided:

- `python -m trading_ai.mt5_readiness --symbol XAUUSD --stop-price-distance 5`: run on Windows with your OWN connected MT5 terminal to calculate min-lot margin and modeled stop-loss in EUR. Never sends orders, refuses unverified round-trip cost information and stale quotes. See [MT5 Readiness](docs/MT5_READINESS.md).
- `python -m trading_ai.agent_bridge --report research_reports/XAUUSD_YYYY-MM-DD.json`: parses a TradingAgents research result into an **unapproved** BUY_ONLY / SELL_ONLY / HALT proposal. Ambiguous or stale AI research yields HALT. This is not an auto-execution route.

**Do not deposit real money based on either command.** Live release still requires an approved broker account, secure account authorization, verified broker contract spec, real market strategy tests, compiled/reviewed EA, and explicit authorized order activation. The public GitHub Pages site is a demonstration and must never handle broker credentials.


## v0.6: Protected MT5 execution module (NOT LIVE-READY)

The \`trading_ai.mt5_execution\` module adds an **optional, single-owner execution adapter** whose live order path is disabled by default. It requires a verified allowlisted account and server, recent human authorization, no positions or pending orders, fresh quotes, broker \`order_calc_profit\` / \`order_calc_margin\` / \`order_check\`, attached Stop Loss and Take Profit, low risk limits, a persistent daily baseline and an idempotency ledger. Unknown broker responses are never automatically retried.

**The module is not wired to the live iPhone web app, is not an active broker service, and has not been compiled or tested in the actual MT5 terminal.** The public PWA remains information-only with a synthetic paper lab. The AI bridge still only produces unapproved research proposals. There is no secure signup/deposit or broker authentication system.

Read [Real-money release checklist](docs/REAL_MONEY_RELEASE.md) for the full gate list. Registration and money transfers can only occur through a regulated broker directly. **No real trading is enabled or verified, and profitability has not been demonstrated.**
