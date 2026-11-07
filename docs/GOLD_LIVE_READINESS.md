# Gold-first release gates — €100 pilot

**Status: NOT live-ready. This document records non-negotiable acceptance gates, not a plan to deposit funds now.**

## User experience at the final release

1. User creates an application account after proper authentication and security review.
2. User is sent to a licensed EU broker's own onboarding and appropriateness checks. **Our app never receives deposits, bank-card details, or broker passwords.**
3. User deposits directly with the broker if approved by that broker. Our app only displays broker-reported funded balance.
4. The server-side integration proves control of the broker account, after authorization. Broker credentials stay in a secret manager, never mobile HTML, GitHub, or browser storage. A generic MT5 password field in a website is NOT an acceptable solution.
5. The app reports the exact symbol, min lot, lot step, contract size, tick value, current EUR conversion rate, spread, stop-level and margin. It refuses `START` unless all values are validated and the expected loss at min-lot and margin are within policy.
6. Only after audited integration, verified broker terms, compiled EA and successful controlled tests can the owner explicitly enable real orders. Read-only mode is default; remote kill switch and forced HALT persist over restarts and connectivity failures.

## Broker screening

- **Admirals Trade.MT5**: public documentation shows €100 minimum deposit. Its gold contract is 100 troy oz per lot; if minimum gold order is 0.01 lot, it represents 1 oz. At approximately $4,070/oz and 1:20 retail leverage, margin alone is ~$203.50 before currency conversion. Verify the *actual* gold symbol specifications for this account: the generic FX 0.01 lot figure is not enough to confirm gold minimum volume.
- **OANDA TMS (EU)**: documents say it supports MT5, offers EU application and **no general minimum opening deposit**; card funding has €25 minimum. It is only a *candidate*. Sources from other OANDA entities saying gold allows 0.001 lot do NOT prove that OANDA TMS permits that volume. Confirm `SYMBOL_VOLUME_MIN` directly on its EU MT5 server and ensure gold is available to the user's approved account.
- Neither broker is selected for live use until the account's specific contract data, spread histories, commission, overnight swaps, order execution, authorization pathway and country availability have been confirmed.

## Risk gates for €100

- Equity per position risk <= 0.25% (€0.25 at €100), measured with MT5 `OrderCalcProfit` to the STOP, plus explicit cost and slippage allowance;
- New-order daily equity drawdown gate 1% (€1 at €100), requiring durable baseline, reconciliation, a best-effort close procedure, and manual reset review;
- One position total; no averaging down, martingale, grid, unrestricted leverage, or attempts to override broker `SYMBOL_VOLUME_MIN`;
- Dynamic market open and news/spread/stop-distance checks, stale AI policy HALT, account type checks and broker/server configuration allowlisting;
- P&L report NET of all trading costs, reported with out-of-sample evidence and drawdown, not a guarantee;
- Stop orders and daily gates do NOT guarantee losses cannot exceed thresholds under gaps or network/execution outages.

## Blockers before real trading (all currently open)

- [ ] Private repository and proper secret management.
- [ ] Licensed broker account selected, user's own approved KYC and funding (user action).
- [ ] Actual EU gold MT5 contract specs and €100 feasibility verified in terminal.
- [ ] EA compiled and reviewed for live logic and persistence; v0.1 *explicitly refuses live accounts*.
- [ ] Historical tick backtests across multiple market regimes, with out-of-sample results and realistic fees/slippage.
- [ ] Paper/demo forward execution and kill-switch failure tests completed.
- [ ] Real application authentication, safe MT5 connector, broker account status and deposits via official broker site.
- [ ] Security review, deployment, monitoring, incident and recovery plans.
- [ ] Independent explicit approval from account owner before *any* live order.

## Primary sources

- https://admiralmarkets.com/bg/start-trading/account-types
- https://admiralmarkets.com/bg/start-trading/commissions-calculations
- https://help.oanda.com/eu/en/faqs/minimum-deposit-requirement.htm
- https://help.oanda.com/eu/en/faqs/deposit-methods-eu.htm
- https://help.oanda.com/eu/en/faqs/mt5-user-guide-eu.htm
- https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors
