"""Process-level evaluation under protocol P1."""

from __future__ import annotations

import numpy as np

from firstalarm.alerts import alerted_procs_day, crossings, first_tstar
from firstalarm.groundtruth import Attack, first_seen_before, mi_indices
from firstalarm.stream import EventStream
from firstalarm.timeutil import ns_to_datetime_us


def _rho_e(es: EventStream, mi: np.ndarray, tstar: int | None) -> float | None:
    if mi.size == 0:
        return None
    if tstar is None:
        return None
    return float(np.sum(es.t[mi] <= tstar) / mi.size)


def _n_seen(es: EventStream, mi: np.ndarray, tstar: int | None) -> int | None:
    if tstar is None or mi.size == 0:
        return None
    return int(np.sum(es.t[mi] <= tstar))


def chain_indices(pred: np.ndarray, start: int, limit: int = 4096) -> list[int]:
    out = []
    cur = int(start)
    seen = set()
    while cur >= 0 and cur not in seen and len(out) < limit:
        seen.add(cur)
        out.append(cur)
        cur = int(pred[cur])
    return out


def _trig_and_chain(d1: bool, idx, pred, mi: np.ndarray) -> tuple[str | None, bool | None]:
    if idx is None:
        return None, None
    i0 = int(idx)
    mi_set = set(mi.tolist())
    if d1:
        has = i0 in mi_set
        return ("M" if has else "nM"), has
    if pred is None:
        return None, None
    chain = chain_indices(pred, i0)
    has = any(j in mi_set for j in chain)
    return ("M" if has else "nM"), has


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
    cr: dict | None = None,
    mem: np.ndarray | None = None,
) -> dict:
    mi = mi if mi is not None else mi_indices(es, attack)
    if cr is None:
        cr = crossings(es, stat, h, d1)
    ts = first_tstar(es, stat, h, attack.P, attack.t0, attack.t1, d1, cr=cr, mem=mem)
    fp_day = alerted_procs_day(cr, win0411, es.day) - set(gt_procs)
    hit = bool(ts["hit"])
    tstar = ts["tstar"]
    delay = None if (not hit or tstar is None) else (int(tstar) - int(attack.t0)) / 1e9
    rho_e = _rho_e(es, mi, tstar) if hit else None
    n_seen = _n_seen(es, mi, tstar) if hit else None
    rho_n = first_seen_before(es, attack.G, tstar) if hit else None
    trig, chain_has = (None, None)
    if hit:
        trig, chain_has = _trig_and_chain(d1, ts["idx"], pred, mi)
    return {
        "hit": hit,
        "tstar": tstar,
        "tstar_str": ns_to_datetime_us(tstar) if tstar is not None else "miss",
        "delay_t0": delay,
        "rho_e": rho_e,
        "rho_n": rho_n,
        "n_seen": n_seen,
        "fp_day": len(fp_day),
        "trig": trig if hit else "miss",
        "chain_has_M": chain_has if hit else None,
        "flag": ts.get("flag"),
        "proc": ts.get("proc"),
        "idx": ts.get("idx"),
        "alerted": sorted(alerted_procs_day(cr, win0411, es.day)),
        "fp_set": sorted(fp_day),
        "channel": None,
    }


def daily_B(
    days: dict[str, EventStream],
    stats: dict[str, np.ndarray],
    h: float,
    d1: bool,
    gt_procs: frozenset[int],
    win0411: tuple[int, int] | None,
    exclude_neutral: set[int],
    crs: dict[str, dict] | None = None,
) -> dict:
    per = {}
    union: set[int] = set()
    union_n: set[int] = set()
    for day, es in days.items():
        cr = crs[day] if crs is not None else crossings(es, stats[day], h, d1)
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
    cr3: dict | None = None,
    mem3: np.ndarray | None = None,
) -> dict:
    a1 = eval_attack(es, attack, s, h1_0, True, gt_procs, win0411, None, mi)
    a3 = eval_attack(es, attack, W, h3, False, gt_procs, win0411, pred, mi, cr=cr3, mem=mem3)
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
    if ch == "D1":
        trig, chain_has, flag, idx = a1["trig"], a1["chain_has_M"], a1["flag"], a1["idx"]
        n_seen, rho_e = a1["n_seen"], a1["rho_e"]
    elif ch == "D3":
        trig, chain_has, flag, idx = a3["trig"], a3["chain_has_M"], a3["flag"], a3["idx"]
        n_seen, rho_e = a3["n_seen"], a3["rho_e"]
    elif ch == "D1+D3":
        has = bool(a1["chain_has_M"] or a3["chain_has_M"])
        trig, chain_has = ("M" if has else "nM"), has
        flag = a1["flag"] if a1["flag"] == a3["flag"] else a1["flag"]
        idx = a1["idx"]
        n_seen = a1["n_seen"]
        rho_e = _rho_e(es, mi, tstar) if hit else None
    else:
        trig, chain_has, flag, idx, n_seen, rho_e = "miss", None, None, None, None, None
    if hit and ch != "D1+D3":
        rho_e = _rho_e(es, mi, tstar)
        n_seen = _n_seen(es, mi, tstar)
    return {
        "hit": hit,
        "tstar": tstar,
        "tstar_str": ns_to_datetime_us(tstar) if tstar is not None else "miss",
        "delay_t0": delay,
        "rho_e": rho_e,
        "rho_n": first_seen_before(es, attack.G, tstar) if hit else None,
        "n_seen": n_seen,
        "fp_day": len(fp),
        "fp_point": len(s1 - s3),
        "fp_mem": len(s3 - s1),
        "fp_both": len(s1 & s3),
        "trig": trig,
        "chain_has_M": chain_has,
        "flag": flag,
        "channel": ch,
        "idx": idx,
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
