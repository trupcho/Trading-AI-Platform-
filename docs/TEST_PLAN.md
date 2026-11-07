# Minimum demo acceptance tests (must pass before enabling EA Demo orders)

| ID | Test | Acceptance criterion |
|----|------|----------------------|
| T01 | Python unit tests | 100% pass |
| T02 | MQL5 MetaEditor compile | Zero compile errors (not yet verified) |
| T03 | Real account accidentally attached | EA refuses initialization / ALL orders blocked |
| T04 | 500 EUR balance, loss budget | Risk budget is €1.25; no order above the budget is accepted under modeled stops + buffer |
| T05 | Broker min lot too large | EA skips order; no risk-limit increase |
| T06 | InpMaxSpreadPoints=0 | EA cannot open any trade |
| T07 | Wide spread | No new orders |
| T08 | Disconnected gateway | Existing broker stops remain, no new positions after policy expiry |
| T09 | Invalid/expired policy | No new orders |
| T10 | Manual HALT approval | No new orders |
| T11 | Daily equity down >=1% vs start | No new orders; EA positions best-effort emergency close |
| T12 | Any open account position | Block new positions |
| T13 | Market closed | No entry; test swap/financing assumptions |
| T14 | MT5 server restart | Stops persist at broker; daily baseline survives within broker day |
| T15 | MT5 Every tick real ticks | Audit entry/exit order log, error retcodes, SL/TP behavior |
| T16 | Demo vs actual symbol mapping | Exact symbol, digits, lot step, tick value, stops and margin verified |
| T17 | Out-of-sample period | Compare EA vs no-AI baseline net after commissions/spread/slippage |
| T18 | Fake negative balance or non-EUR account | No entry |

## Performance report fields

- start/end dates and data source
- transaction count and distribution by time of day
- realized P&L, unrealized P&L, fee and spread contributions
- net expectancy per trade, profit factor, gross/net average win/loss
- win rate, equity curve and maximum drawdown
- maximum consecutive losses, time in market, average execution delay
- rejection reasons (% min lot, spread, margin, stale signal)
- data quality: missing bars, out-of-sequence ticks, market hours
- both in-sample and genuinely untouched out-of-sample results

No numeric performance estimates are provided before broker-specific test data exists.
