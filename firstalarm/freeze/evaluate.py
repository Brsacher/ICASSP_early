# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Process-level evaluation, B/B′, attribution, C5."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from firstalarm.freeze.alerts import alerted_procs_day, crossings, first_tstar
from firstalarm.freeze.calibrate import max_by_proc
from firstalarm.freeze.groundtruth import Attack, GroundTruth, first_seen_before, mi_indices
from firstalarm.freeze.stream import EventStream
from firstalarm.freeze.timeutil import ns_to_datetime_us


def _rho_e(es: EventStream, mi: np.ndarray, tstar: int | None) -> float | None:
    if mi.size == 0:
        return None
    if tstar is None:
        return None
    return float(np.sum(es.t[mi] <= tstar) / mi.size)


def _chain_indices(pred: np.ndarray, start: int, limit: int = 4096) -> list[int]:
    out = []
    cur = int(start)
    seen = set()
    while cur >= 0 and cur not in seen and len(out) < limit:
        seen.add(cur)
        out.append(cur)
        cur = int(pred[cur])
    return out


def eval_attack(
    es: EventStream,
    attack: Attack,
    stat: np.ndarray,
    h: float,
    d1: bool,
    gt_procs: frozenset[int],
    win0411: tuple[int, int] | None,
    pred: np.ndarray | None = None,
    mi: np.ndarray | None = None,
) -> dict:
    mi = mi if mi is not None else mi_indices(es, attack)
    ts = first_tstar(es, stat, h, attack.P, attack.t0, attack.t1, d1, mi)
    cr = crossings(es, stat, h, d1)
    fp_day = alerted_procs_day(cr, win0411, es.day) - set(gt_procs)
    hit = bool(ts["hit"])
    tstar = ts["tstar"]
    delay = None if (not hit or tstar is None) else (int(tstar) - int(attack.t0)) / 1e9
    rho_e = _rho_e(es, mi, tstar) if hit else None
    rho_n = first_seen_before(es, attack.G, tstar) if hit else None
    trig = None
    if hit and ts["idx"] is not None:
        i0 = int(ts["idx"])
        if d1:
            trig = "M" if i0 in set(mi.tolist()) else "nM"
        elif pred is not None:
            chain = _chain_indices(pred, i0)
            trig = "M" if any(j in set(mi.tolist()) for j in chain) else "nM"
    return {
        "hit": hit,
        "tstar": tstar,
        "tstar_str": ns_to_datetime_us(tstar) if tstar is not None else "miss",
        "delay_t0": delay,
        "rho_e": rho_e,
        "rho_n": rho_n,
        "fp_day": len(fp_day),
        "trig": trig if hit else "miss",
        "flag": ts.get("flag"),
        "already": ts.get("already") or [],
        "proc": ts.get("proc"),
        "idx": ts.get("idx"),
        "alerted": sorted(alerted_procs_day(cr, win0411, es.day)),
        "fp_set": sorted(fp_day),
    }


def daily_B(
    days: dict[str, EventStream],
    stats: dict[str, np.ndarray],
    h: float,
    d1: bool,
    gt_procs: frozenset[int],
    win0411: tuple[int, int] | None,
    exclude_neutral: set[int],
) -> dict:
    per = {}
    union: set[int] = set()
    union_n: set[int] = set()
    for day, es in days.items():
        cr = crossings(es, stats[day], h, d1)
        a = alerted_procs_day(cr, win0411, day) - set(gt_procs)
        an = a - exclude_neutral
        per[day] = {"B": len(a), "Bp": len(an)}
        union |= a
        union_n |= an
    mean_b = float(np.mean([v["B"] for v in per.values()])) if per else 0.0
    return {"per_day": per, "union_B": len(union), "union_Bp": len(union_n), "mean_B": mean_b}


def eval_d4(
    es: EventStream,
    attack: Attack,
    s: np.ndarray,
    W: np.ndarray,
    h1_0: float,
    h3: float,
    gt_procs: frozenset[int],
    win0411,
    pred: np.ndarray,
    mi: np.ndarray,
) -> dict:
    a1 = eval_attack(es, attack, s, h1_0, True, gt_procs, win0411, None, mi)
    a3 = eval_attack(es, attack, W, h3, False, gt_procs, win0411, pred, mi)
    hit = a1["hit"] or a3["hit"]
    t1, t3 = a1["tstar"], a3["tstar"]
    if a1["hit"] and a3["hit"]:
        tstar = min(t1, t3)
        ch = "D1+D3" if t1 == t3 else ("D1" if t1 < t3 else "D3")
    elif a1["hit"]:
        tstar, ch = t1, "D1"
    elif a3["hit"]:
        tstar, ch = t3, "D3"
    else:
        tstar, ch = None, "miss"
    delay = None if tstar is None else (int(tstar) - int(attack.t0)) / 1e9
    s1, s3 = set(a1["fp_set"]), set(a3["fp_set"])
    fp = s1 | s3
    return {
        "hit": hit,
        "tstar": tstar,
        "tstar_str": ns_to_datetime_us(tstar) if tstar is not None else "miss",
        "delay_t0": delay,
        "rho_e": _rho_e(es, mi, tstar) if hit else None,
        "rho_n": first_seen_before(es, attack.G, tstar) if hit else None,
        "fp_day": len(fp),
        "fp_point": len(s1 - s3),
        "fp_mem": len(s3 - s1),
        "fp_both": len(s1 & s3),
        "trig": ch,
        "flag": None,
        "already": (a1.get("already") or []) + (a3.get("already") or []),
        "alerted": sorted(set(a1["alerted"]) | set(a3["alerted"])),
        "fp_set": sorted(fp),
        "ch_d1": a1["hit"],
        "ch_d3": a3["hit"],
    }


def d4_fp_split(a1: set[int], a3: set[int]) -> dict:
    return {
        "B": len(a1 | a3),
        "B_point": len(a1 - a3),
        "B_mem": len(a3 - a1),
        "B_both": len(a1 & a3),
    }


def c5_stats(es: EventStream, pas, top: int = 5) -> dict:
    dens = float(pas.stats.get("density") or 0.0)
    mx = max_by_proc(es, pas.W)
    ranked = sorted(mx.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    contribs = []
    ok = True
    for p, final in ranked:
        idxs = [i for i in range(es.n) if int(es.proc[i]) == p]
        if not idxs or final <= 0:
            contribs.append({"proc": p, "final": final, "contrib": 0.0})
            continue
        i_max = max(idxs, key=lambda i: float(pas.W[i]))
        inherit = 0.0
        cur = int(i_max)
        seen = set()
        while cur >= 0 and cur not in seen:
            seen.add(cur)
            if int(pas.pred_kind[cur]) in (1, 2):
                # inherited value entering this step ≈ W - inc
                inherit = max(inherit, max(0.0, float(pas.W[cur]) - float(pas.inc[cur])))
            cur = int(pas.pred[cur])
        c = min(inherit, final) / final if final > 0 else 0.0
        contribs.append({"proc": p, "final": final, "contrib": c, "inherit": inherit})
        if c >= 0.10:
            ok = False
    return {
        "density": dens,
        "density_ok": dens <= 0.05,
        "contrib": contribs,
        "contrib_ok": ok,
        "pass": bool(dens <= 0.05 and ok),
    }


def bridge_endpoints(es: EventStream, cr: dict[int, list]) -> set[int]:
    nodes = set()
    for evs in cr.values():
        for i, _t in evs:
            nodes.add(int(es.src[i]))
            nodes.add(int(es.dst[i]))
    return nodes


def fmt_num(x, nd=4):
    if x is None:
        return "miss"
    if isinstance(x, float) and (np.isnan(x) or not np.isfinite(x)):
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}g}" if abs(x) < 1e-3 or abs(x) >= 1e4 else f"{x:.4f}".rstrip("0").rstrip(".")
    return str(x)


def fmt_delay(x):
    if x is None:
        return "miss"
    return f"{x:.1f}"
