"""Q6 duration normalization."""

from __future__ import annotations

import re
from datetime import timedelta

_DURATION_TOKEN = re.compile(r"(\d+(?:\.\d+)?)(ns|us|ms|s|m|h)")

_UNIT_SECONDS: dict[str, float] = {
    "ns": 1e-9,
    "us": 1e-6,
    "ms": 1e-3,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
}


def parse_duration(s: str) -> float:
    """Parse strings like '1h2m3.5s' into seconds."""
    s = s.strip()
    if not s:
        raise ValueError("empty duration string")
    if s == "0":
        return 0.0
    sign = 1.0
    if s[0] in "+-":
        if s[0] == "-":
            sign = -1.0
        s = s[1:]
        if not s:
            raise ValueError("duration has only a sign")
    total = 0.0
    pos = 0
    while pos < len(s):
        m = _DURATION_TOKEN.match(s, pos)
        if m is None:
            raise ValueError(f"unparseable duration {s!r} at offset {pos}")
        total += float(m.group(1)) * _UNIT_SECONDS[m.group(2)]
        pos = m.end()
    return sign * total


def to_seconds(value: object) -> float:
    """Coerce one engine's Q6 native scalar into total seconds."""
    if value is None:
        return 0.0
    if isinstance(value, bool):
        # A bool here is almost certainly a projector bug, not a duration.
        raise TypeError(f"Q6 to_seconds: refusing to coerce bool {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0.0
        if s[-1].isalpha():
            return parse_duration(s)
        return float(s)
    raise TypeError(f"Q6 to_seconds: cannot coerce {type(value).__name__} {value!r}")


def to_milliseconds(value: object) -> int:
    """Canonical Q6 value: integer milliseconds, truncated toward zero."""
    return int(to_seconds(value) * 1000)
