"""US/Eastern conversions, matching pidsmaker.utils.utils without importing it."""

from __future__ import annotations

from datetime import datetime
from time import mktime
import time

import numpy as np
import pytz

EASTERN = pytz.timezone("US/Eastern")
_TZ = EASTERN


def datetime_to_ns_us(date: str) -> int:
    time_array = time.strptime(date, "%Y-%m-%d %H:%M:%S")
    dt = datetime.fromtimestamp(mktime(time_array))
    ts = _TZ.localize(dt).timestamp()
    return int(ts * 1_000_000_000)


def ns_to_datetime_us(ns: int) -> str:
    dt = datetime.fromtimestamp(int(ns) // 1_000_000_000, _TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def ns_to_dt_us(ns: int) -> datetime:
    return datetime.fromtimestamp(int(ns) // 1_000_000_000, _TZ)


def ns_to_day_us(t: np.ndarray) -> np.ndarray:
    sec = (t.astype(np.int64) // 1_000_000_000).astype(np.int64)
    out = np.empty(len(sec), dtype=object)
    for i, s in enumerate(sec):
        out[i] = datetime.fromtimestamp(int(s), _TZ).strftime("%Y-%m-%d")
    return out
