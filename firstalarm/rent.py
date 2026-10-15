"""Priors, instance baseline, and cap."""

from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from firstalarm.config import N_MIN_KIND, WARMUP
from firstalarm.stream import EventStream


class _Median:
    """O(log n) running median (max-heap + min-heap)."""

    __slots__ = ("lo", "hi")

    def __init__(self):
        self.lo: list[float] = []
        self.hi: list[float] = []

    def add(self, x: float) -> None:
        if not self.lo or x <= -self.lo[0]:
            heapq.heappush(self.lo, -x)
        else:
            heapq.heappush(self.hi, x)
        if len(self.lo) > len(self.hi) + 1:
            heapq.heappush(self.hi, -heapq.heappop(self.lo))
        elif len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def median(self) -> float:
        if not self.lo:
            return 0.0
        if len(self.lo) > len(self.hi):
            return float(-self.lo[0])
        return 0.5 * (-self.lo[0] + self.hi[0])

    def __len__(self) -> int:
        return len(self.lo) + len(self.hi)


@dataclass
class Priors:
    prior_mode: str
    kind: dict[str, float]
    typ: dict[int, float]
    global_prior: float
    n_kind: dict[str, int]
    n_type: dict[int, int]
    cap_c: float | None
    clip_mass: float


def _q75_mean(xs: np.ndarray) -> float:
    if xs.size == 0:
        return float("nan")
    return float(max(np.quantile(xs, 0.75, method="linear"), float(xs.mean())))


def build_priors(val: EventStream, prior_mode: str) -> Priors:
    by_kind: dict[str, list[float]] = defaultdict(list)
    by_type: dict[int, list[float]] = defaultdict(list)
    for i in range(val.n):
        by_kind[str(val.kind[i])].append(float(val.s[i]))
        by_type[int(val.etype[i])].append(float(val.s[i]))
    n_kind = {k: len(v) for k, v in by_kind.items()}
    n_type = {k: len(v) for k, v in by_type.items()}
    kind = {k: _q75_mean(np.asarray(v, dtype=np.float64)) for k, v in by_kind.items() if n_kind[k] >= N_MIN_KIND}
    typ = {k: _q75_mean(np.asarray(v, dtype=np.float64)) for k, v in by_type.items() if n_type[k] > 0}
    g = _q75_mean(val.s.astype(np.float64))
    return Priors(prior_mode, kind, typ, g, n_kind, n_type, None, 0.0)


def prior_of(pr: Priors, kind: str, etype: int) -> float:
    if pr.prior_mode == "kind" and kind in pr.kind:
        return pr.kind[kind]
    if etype in pr.typ:
        return pr.typ[etype]
    return pr.global_prior


def delta_on_stream(es: EventStream, pr: Priors) -> np.ndarray:
    """δ_p per event: prior, then from the 6th (proc,etype) event max(prior, median of previous s)."""
    delta = np.empty(es.n, dtype=np.float64)
    hist: dict[tuple[int, int], _Median] = {}
    for i in range(es.n):
        key = (int(es.proc[i]), int(es.etype[i]))
        prev = hist.get(key)
        p0 = prior_of(pr, str(es.kind[i]), int(es.etype[i]))
        if prev is None or len(prev) < WARMUP:
            delta[i] = p0
        else:
            delta[i] = max(p0, prev.median())
        if prev is None:
            prev = hist[key] = _Median()
        prev.add(float(es.s[i]))
    return delta


def cap_q99(val: EventStream, delta: np.ndarray) -> tuple[float, float]:
    x = val.s.astype(np.float64) - delta
    pos = x[x > 0.0]
    if pos.size == 0:
        return 0.0, 0.0
    c = float(np.quantile(pos, 0.99, method="linear"))
    mass = float(np.maximum(x - c, 0.0).sum())
    den = float(np.maximum(x, 0.0).sum())
    ratio = mass / den if den > 0 else 0.0
    return c, ratio


def clip_inc(x: np.ndarray, cap_c: float | None) -> np.ndarray:
    inc = x.astype(np.float64).copy()
    if cap_c is None:
        return inc
    pos = inc > 0.0
    inc[pos] = np.minimum(inc[pos], float(cap_c))
    return inc
