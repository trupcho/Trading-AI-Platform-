"""Converts TradingAgents research JSON into *unapproved* directional proposals.

This module has no broker access and no gateway approval path. LLM prose is not
trusted as executable instructions. Anything ambiguous, stale or malformed HALTs.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

PROXIES = {'XAUUSD': 'GC=F', 'NAS100': '^NDX'}
ACTIONS = {'BUY': 'BUY_ONLY', 'SELL': 'SELL_ONLY', 'HOLD': 'HALT'}


def _action(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    token = raw.strip().upper()
    if token in ACTIONS:
        return token
    # Be conservative: optional machine-readable JSON with exactly one key.
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(obj, dict) and set(obj) == {'action'} and isinstance(obj['action'], str):
        token = obj['action'].strip().upper()
        if token in ACTIONS:
            return token
    return None


def review_research(report: Any, *, today: date | None = None) -> dict:
    """Review only. Never return an executable approval or trade instruction."""
    output = dict(mode='HALT', approved=False, executable=False,
                  action='UNRESOLVED', reason='UNTRUSTED_OR_UNREADABLE_RESEARCH')
    if not isinstance(report, dict):
        return output
    market = report.get('requested_market')
    if market not in PROXIES or report.get('research_proxy') != PROXIES.get(market):
        output['reason'] = 'UNSUPPORTED_MARKET_OR_PROXY_MISMATCH'
        return output
    output['symbol'] = market
    try:
        as_of = date.fromisoformat(report.get('as_of', ''))
    except (TypeError, ValueError):
        output['reason'] = 'MISSING_OR_INVALID_DATE'
        return output
    today = today or datetime.now(timezone.utc).date()
    if as_of != today:
        output['reason'] = 'STALE_RESEARCH'
        return output
    action = _action(report.get('raw_decision'))
    if action is None:
        output['reason'] = 'AMBIGUOUS_LLM_OUTPUT'
        return output
    output.update(action=action, mode=ACTIONS[action], reason='RESEARCH_PROPOSAL_ONLY')
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description='Review TradingAgents research. Never authorizes MT5 orders.')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        output = review_research(json.loads(args.report.read_text(encoding='utf-8')))
    except (OSError, json.JSONDecodeError, UnicodeError):
        output = review_research(None)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if output.get('action') == 'HOLD' else 2  # not an order/approval API

if __name__ == '__main__':
    raise SystemExit(main())
