# Development roadmap

## v0.1 — delivered source starter
- [x] Python demo-only loopback gateway with expiry, auth and heartbeat
- [x] Read-only local responsive web status page
- [x] MQL5 EA source with conservative demo checks; compiler verification pending
- [x] Research-only TradingAgents adapter
- [x] Python unit tests and CI
- [x] User created GitHub repository; source import pending verification
- [ ] Change repository visibility to private (current repository was public at import)
- [ ] Connect actual broker Demo and confirm symbol specs
- [ ] Compile MQL5 source in MetaEditor and debug any broker-specific details

## v0.2 — verified demo
- [ ] Automated broker symbol spec export and spread sampling
- [ ] EA offline historical testing and tick replay reconciliation
- [ ] Persistent journal (SQLite/Postgres), idempotent gateway updates and restart recovery
- [ ] Secure structured AI policy adapter with model/data provenance
- [ ] Paper-trade trades reporting & logs

## v0.3 — application
- [ ] Real backend, authenticated remote read-only API
- [ ] React Native Expo iPhone app
- [ ] Next.js responsive web/desktop app
- [ ] Push notifications and emergency demo HALT

## v1.0 — decision gate, no promised live launch
- [ ] Extended prospective demo results and independent review
- [ ] Stress-test broker outage, slippage, disconnections, stop orders
- [ ] Confirm costs, taxes, broker permissions, KYC, user risk tolerance
- [ ] Only after user explicitly decides: separate live design and security review
