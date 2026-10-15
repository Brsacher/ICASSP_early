# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Validation-day thresholds, C1, and pair selection."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from firstalarm.freeze.alerts import crossings
from firstalarm.freeze.config import BUDGETS, C1_HI, C1_LO, PAIRS
from firstalarm.freeze.stream import EventStream


def max_by_proc(es: EventStream, stat: np.ndarray) -> dict[int, float]:
    mx: dict[int, float] = {}
    for i in range(es.n):
        if int(es.proc_type[i]) != 0:
            continue
        p = int(es.proc[i])
        v = float(stat[i])
        if p not in mx or v > mx[p]:
            mx[p] = v
    return mx


def h_from_max(vals: list[float], budgets=BUDGETS) -> dict[int, float]:
    xs = sorted((float(v) for v in vals), reverse=True)
    out = {}
    for b in budgets:
        if len(xs) <= b:
            out[int(b)] = float(np.nextafter(0.0, 1.0))
        else:
            out[int(b)] = float(np.nextafter(xs[b], np.inf))
    return out


def calib_from_stat(es: EventStream, stat: np.ndarray) -> dict[int, float]:
    mx = max_by_proc(es, stat)
    return h_from_max(list(mx.values()))


def c1_ratios(h1: dict, h2: dict, h3: dict, b: int = 2) -> dict:
    a = float(h1[b])
    r2 = float(h2[b]) / a if a > 0 else float("inf")
    r3 = float(h3[b]) / a if a > 0 else float("inf")

    def ok(r: float) -> bool:
        return C1_LO <= r <= C1_HI and np.isfinite(r)

    fold = max(_fold(r2), _fold(r3))
    return {"r2": r2, "r3": r3, "pass": bool(ok(r2) and ok(r3)), "fold": fold, "h1": a, "h2": float(h2[b]), "h3": float(h3[b])}


def _fold(r: float) -> float:
    if not np.isfinite(r) or r <= 0:
        return float("inf")
    return max(r, 1.0 / r)


def select_pair(per_seed_c1: dict[int, dict[tuple[str, str], dict]]) -> dict:
    """per_seed_c1[seed][(cap, prior)] = {pass, fold, r2, r3, ...}"""
    chosen = None
    marked = False
    detail = {}
    n_by_pair = {}
    for pair in PAIRS:
        n_pass = 0
        folds = []
        rows = {}
        for seed, d in per_seed_c1.items():
            row = d[pair]
            rows[seed] = row
            n_pass += int(row["pass"])
            folds.append(row["fold"])
        med_fold = float(np.median(np.asarray(folds, dtype=np.float64)))
        detail[f"{pair[0]}_{pair[1]}"] = {
            "n_pass": n_pass,
            "median_fold": med_fold,
            "per_seed": {str(k): v for k, v in rows.items()},
        }
        n_by_pair[pair] = n_pass
    best_n = max(n_by_pair.values()) if n_by_pair else 0
    if best_n >= 4:
        chosen = next(p for p in PAIRS if n_by_pair[p] == best_n)
    else:
        marked = True
        best = None
        best_f = float("inf")
        for pair in PAIRS:
            f = detail[f"{pair[0]}_{pair[1]}"]["median_fold"]
            if f < best_f:
                best_f = f
                best = pair
        chosen = best
    return {
        "cap": chosen[0],
        "prior": chosen[1],
        "c1_pass": (not marked),
        "mark": "C1 未通过" if marked else "C1 通过",
        "pairs": detail,
    }


def who_set(es: EventStream, stat: np.ndarray, kinds: np.ndarray, pred=None, pred_kind=None, top: int = 5) -> list[dict]:
    mx = max_by_proc(es, stat)
    ranked = sorted(mx.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    # event composition + chain for the event that achieved the max
    rows = []
    for p, v in ranked:
        idxs = [i for i in range(es.n) if int(es.proc[i]) == p]
        et_cnt: dict[str, int] = defaultdict(int)
        kind = "unknown"
        for i in idxs:
            et_cnt[str(int(es.etype[i]))] += 1
            kind = str(es.kind[i])
        chain = []
        if pred is not None and idxs:
            i_max = max(idxs, key=lambda i: float(stat[i]))
            cur = int(i_max)
            seen = set()
            while cur >= 0 and cur not in seen and len(chain) < 16:
                seen.add(cur)
                chain.append(
                    {
                        "i": cur,
                        "t": int(es.t[cur]),
                        "etype": int(es.etype[cur]),
                        "kind": int(pred_kind[cur]) if pred_kind is not None else None,
                        "pred": int(pred[cur]),
                    }
                )
                cur = int(pred[cur])
        rows.append({"proc": p, "max": v, "program": kind, "n_events": len(idxs), "etypes": dict(et_cnt), "chain": chain})
    return rows
