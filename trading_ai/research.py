"""Optional TradingAgents research experiment: DOES NOT approve or execute trades.

Important: GC=F (gold futures) and ^NDX (Nasdaq 100 index) are research
proxies; they are NOT the broker's tradable XAUUSD/NAS100 CFD quotes.
"""
import argparse
from datetime import date
import json
from pathlib import Path

PROXIES = {"XAUUSD": "GC=F", "NAS100": "^NDX"}


def run_research(market: str, date_iso: str, output_dir: Path) -> Path:
    if market not in PROXIES:
        raise ValueError("market must be XAUUSD or NAS100")
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
    except ImportError as e:
        raise RuntimeError("TradingAgents not installed; see docs/AI_INTEGRATION.md") from e
    cfg = DEFAULT_CONFIG.copy()
    # Deliberately do not guess provider/model settings; use official environment/config.
    ta = TradingAgentsGraph(debug=False, config=cfg)
    state, decision = ta.propagate(PROXIES[market], date_iso)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{market}_{date_iso}.json"
    target.write_text(json.dumps({
        "requested_market": market,
        "research_proxy": PROXIES[market],
        "as_of": date_iso,
        "raw_decision": str(decision),
        "disclaimer": "Research only: no MT5 broker quote or execution permission"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description="Research only; never trades")
    parser.add_argument("--market", choices=PROXIES, required=True)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=Path("research_reports"))
    args = parser.parse_args()
    print(run_research(args.market, args.date, args.output))


if __name__ == "__main__":
    main()
