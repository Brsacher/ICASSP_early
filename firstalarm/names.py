"""Program-name normalization."""

from __future__ import annotations

import re

_SKIP = frozenset({"", "none", "null", "subject", "file", "netflow", "type"})
_VER_TAIL = re.compile(r"(?:\d+\.)+\d+$")
_DIGIT_TAIL = re.compile(r"\d+$")


def program_name(label: object) -> str:
    if label is None:
        return "unknown"
    s = str(label).strip()
    if not s:
        return "unknown"
    tokens = s.split()
    raw = None
    for tok in tokens:
        t = tok.strip()
        if t.lower() in _SKIP:
            continue
        raw = t
        break
    if raw is None:
        return "unknown"
    raw = raw.replace("(deleted)", "").strip()
    base = raw.rsplit("/", 1)[-1].strip()
    if not base:
        return "unknown"
    base = _VER_TAIL.sub("", base)
    base = _DIGIT_TAIL.sub("", base)
    base = base.rstrip(".-_")
    return base.lower() if base else "unknown"
