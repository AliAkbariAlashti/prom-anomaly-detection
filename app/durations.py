"""Parse PromQL-style duration strings (e.g. "1w", "2h", "30m", "45s") into seconds."""
from __future__ import annotations

import re

_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}

_PATTERN = re.compile(r"^(\d+)([smhdw])$")


def parse_duration(duration: str) -> int:
    match = _PATTERN.match(duration.strip())
    if not match:
        raise ValueError(
            f"Invalid duration '{duration}'. Expected format like '30s', '5m', '2h', '1d', '1w'."
        )
    value, unit = match.groups()
    return int(value) * _UNIT_SECONDS[unit]
