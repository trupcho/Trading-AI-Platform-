"""Bounded short-lived directional policies; never direct trading instructions."""
from __future__ import annotations
from dataclasses import dataclass
import re
import time

ALLOWED_MODES = frozenset({"HALT", "BUY_ONLY", "SELL_ONLY", "BOTH"})
SYMBOL = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


@dataclass(frozen=True)
class DirectionPolicy:
    symbol: str
    mode: str
    issued_at: int
    expires_at: int

    def __post_init__(self):
        if not SYMBOL.fullmatch(self.symbol):
            raise ValueError("invalid symbol")
        if self.mode not in ALLOWED_MODES:
            raise ValueError("invalid mode")
        if self.expires_at < self.issued_at or self.expires_at - self.issued_at > 900:
            raise ValueError("invalid lifetime")

    @classmethod
    def issued(cls, symbol: str, mode: str, ttl_seconds: int = 300):
        if not 1 <= ttl_seconds <= 900:
            raise ValueError("ttl must be 1..900")
        now = int(time.time())
        return cls(symbol=symbol, mode=mode, issued_at=now, expires_at=now + ttl_seconds)

    def active(self, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else now
        return self.issued_at - 60 <= now < self.expires_at

    def mt5_wire(self, now: int | None = None) -> str:
        mode = self.mode if self.active(now) else "HALT"
        # MT5 validates expiry independently. Never extend a policy implicitly.
        return f"V1|{self.symbol}|{mode}|{self.issued_at}|{self.expires_at}"


def halted(symbol: str) -> DirectionPolicy:
    return DirectionPolicy.issued(symbol, "HALT", 60)
