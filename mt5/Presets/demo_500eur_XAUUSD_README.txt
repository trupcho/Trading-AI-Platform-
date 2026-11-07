TRADING AI DEMO MT5 PRESET (configure via EA Inputs)

ATTENTION: this is a documentation preset, not a validated MT5 .set file.

Account type = DEMO only
Account currency = EUR
Start balance = 500 EUR
Chart = broker's XAUUSD symbol on M1
InpEnableDemoOrders = false (KEEP OFF until the tester checks pass)
InpTesterPolicy = TAI_HALT (for Strategy Tester set BOTH on explicit manual test)
InpRiskPct = 0.25
InpDailyLossPct = 1.00
InpMaxMarginPct = 35.00
InpMaxSpreadPoints = 0 (FAIL-CLOSED; set ONLY using measured broker spread in POINTS)
InpAtrSLMultiplier = 1.50
InpAtrTPMultiplier = 2.00
InpRiskCostBuffer = 1.20
InpPollSeconds = 15
InpGatewayBase = http://127.0.0.1:8765
InpGatewayKey = same private 24+ char token as environment variable

Note: with 500 EUR and strict risk limits, XAUUSD 0.01-lot may be too large.
In such a case the EA should make ZERO trades; do not loosen safeguards just
because it seems inactive. NAS100 must be separately validated for each broker.
