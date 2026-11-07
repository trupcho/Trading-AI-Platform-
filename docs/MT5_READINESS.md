# Trading AI — read-only €100 MT5 broker feasibility check

This checks whether the actual broker's **minimum XAUUSD volume** fits a €100 pilot's risk and margin policy. It does not execute or approve real trades. The `ready_for_live` field is always `false`.

## Run with your own Windows MT5 terminal

1. Create your own broker account and complete all KYC/suitability checks **with the broker**, not through GitHub Pages. Do not fund the account based only on this check.
2. Sign in to the MT5 terminal yourself; find the precise tradable gold symbol in Market Watch (e.g. `XAUUSD`, `GOLD`, `GOLD.pro`).
3. On the same Windows PC, install 64-bit Python 3.11+ and run `py -m pip install MetaTrader5`.
4. Run `py -m trading_ai.mt5_readiness --symbol XAUUSD --stop-price-distance 5`, replacing the symbol to match the broker.
5. Read the resulting JSON. It is normal for it to return `ROUNDTRIP_COSTS_NOT_VERIFIED`. Only supply `--roundtrip-cost-buffer-eur 0.xx` if you have a conservative broker-confirmed total spread/commission/slippage buffer. The probe cannot verify this cost independently.

It reads `initialize`, `account_info`, `symbol_info`, `symbol_info_tick`, `order_calc_margin`, `order_calc_profit` and then calls `shutdown`. No login, order_send, or credential handling. Account identifiers are not included in the JSON output.

The check rejects stale price quotes, accounts in currencies other than EUR, impossible stop distances, broker-calculation failures, unverified costs and minimum positions that exceed either a €0.25 estimated stop-loss budget or €35 margin budget for a €100 pilot. If account equity is below €100, budgets decrease proportionately. These are estimates, not guarantees: spreads, gaps and losses can exceed the modeled amounts.

This does **not** validate signal profitability, full CFD costs, regulations, account security, remote controls, trailing positions or MT5 EA compatibility. The existing Demo EA still refuses live orders. Before live deployment we need verified EU broker terms, MT5 compile and historical/forward tests, secure backend authentication and explicit owner approval of live access.

References: https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py and https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py
