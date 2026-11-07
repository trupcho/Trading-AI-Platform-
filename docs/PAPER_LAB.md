# Gold Paper Lab — v0.4

## Purpose
Phone-installable **offline synthetic-trading demonstration** at \`web/paper.html\`, accessible through the GitHub Pages PWA home screen. Nothing here is live market data, broker execution, MT5 integration, or TradingAgents autonomous AI.

## User flow
1. Open the existing GitHub Pages installation / home screen icon.
2. Tap **Пробвай Gold Paper Lab**.
3. Tap **Start Paper** for simulated prices with algorithmic EMA signals, or **Превърти 200 тика** for quick examples.
4. Inspect balance/equity, simulated order exits, simulated protective stops, risk halt, and CSV export.
5. **Stop** pauses; **Нулирай €100** deletes local paper history.

## Risk/implementation details
- €100 synthetic initial capital and 0.25% nominal risk allowance for each virtual entry; one open position.
- Virtual 1% daily equity-loss halt. There is no broker enforcement, actual leverage or broker-minimum-lot validation.
- Synthetic XAUUSD-style prices near $4,000, never real quotes, with *illustrative* $0.28 spread, €0.02 per-trade fee, USD/EUR multiplier of 0.90.
- Simple EMA(9,21) synthetic-data signal; **not TradingAgents research**, not a trained or validated AI strategy.
- Price updates only while the mobile page is visible and the local timer is running. Browser may suspend timers when backgrounded.
- Local device storage only. No login, bank/card data, broker credentials, server, funding, deposits, or real orders.
- Generates both gains and losses; a sample run is not proof of profitability.

## Live trading remains blocked
Real-money usage requires broker approval and suitability/KYC, MT5 EA compilation, historical & forward tests, broker contract-size/min-volume/margin validation for €100, secure remote gateway, server execution, authorization, monitoring and kill switches. No credentials belong in GitHub Pages.

## QA
- JS syntax checked by compiling the \`<script>\` content.
- Simulated UI state tested with mock DOM: initial €100; 200-tick test produced closed virtual trades; reset restored €100.
- GitHub Pages workflow uploads \`web/\` from main.
