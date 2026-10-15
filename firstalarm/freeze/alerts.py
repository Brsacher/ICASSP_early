# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Process-level crossings and t* (60 s pre-window rule)."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from firstalarm.freeze.config import PRE_T0_NS
from firstalarm.freeze.stream import EventStream


def crossings(es: EventStream, stat: np.ndarray, h: float, d1: bool) -> dict[int, list[tuple[int, int]]]:
    """proc -> [(event_index, time_ns), ...] upward crossings (or every s>=h for D1)."""
    out: dict[int, list[tuple[int, int]]] = defaultdict(list)
    last_below: dict[int, bool] = {}
    for i in range(es.n):
        if int(es.proc_type[i]) != 0:
            continue
        p = int(es.proc[i])
        v = float(stat[i])
        if d1:
            if v >= h:
                out[p].append((i, int(es.t[i])))
            continue
        below = last_below.get(p, True)
        ge = v >= h
        if below and ge:
            out[p].append((i, int(es.t[i])))
        last_below[p] = not ge
    return dict(out)


def stat_at_t0(es: EventStream, stat: np.ndarray, proc: int, t0: int) -> float:
    """Statistic of the last event of proc with t <= t0 (0 if none)."""
    last = 0.0
    for i in range(es.n):
        if int(es.t[i]) > t0:
            break
        if int(es.proc[i]) == proc:
            last = float(stat[i])
    return last


def first_tstar(
    es: EventStream,
    stat: np.ndarray,
    h: float,
    P: frozenset[int],
    t0: int,
    t1: int,
    d1: bool,
    mi_idx: np.ndarray,
) -> dict:
    """Earliest alert among P in the window, with 60s / already-on rules."""
    cr = crossings(es, stat, h, d1)
    best_t = None
    best_i = None
    best_p = None
    already = []
    for p in P:
        evs = cr.get(p, [])
        if not evs:
            continue
        still = stat_at_t0(es, stat, p, t0) >= h
        in_win = [(i, t) for i, t in evs if t0 <= t <= t1]
        pre60 = [(i, t) for i, t in evs if (t0 - PRE_T0_NS) <= t < t0]
        earlier = [(i, t) for i, t in evs if t < (t0 - PRE_T0_NS)]
        t_use = None
        i_use = None
        flag = None
        if pre60 and still:
            t_use, i_use, flag = t0, pre60[0][0], "pre60"
        elif earlier and still:
            # already in alarm; secondary t* = first M_i of this proc with t>=t0
            flag = "already"
            sec = None
            for j in mi_idx.tolist():
                if int(es.t[j]) >= t0 and int(es.proc[j]) == p:
                    sec = (int(j), int(es.t[j]))
                    break
            already.append({"proc": p, "secondary_t": None if sec is None else sec[1], "secondary_i": None if sec is None else sec[0]})
            if sec is not None:
                t_use, i_use = sec[1], sec[0]
        elif in_win:
            i_use, t_use = in_win[0]
            flag = "window"
        if t_use is None:
            continue
        if best_t is None or t_use < best_t:
            best_t, best_i, best_p = t_use, i_use, p
            best_flag = flag
    if best_t is None:
        return {"hit": False, "tstar": None, "idx": None, "proc": None, "already": already, "flag": None}
    return {
        "hit": True,
        "tstar": int(best_t),
        "idx": int(best_i) if best_i is not None else None,
        "proc": int(best_p) if best_p is not None else None,
        "already": already,
        "flag": best_flag,
    }


def alerted_procs(cr: dict[int, list], t0_excl: int | None = None, t1_excl: int | None = None) -> set[int]:
    out = set()
    for p, evs in cr.items():
        if t0_excl is None:
            if evs:
                out.add(p)
            continue
        if any(not (t0_excl <= t <= t1_excl) for _i, t in evs):
            out.add(p)
        elif evs and not any(t0_excl <= t <= t1_excl for _i, t in evs):
            out.add(p)
    return out


def alerted_procs_day(cr: dict[int, list], win0411: tuple[int, int] | None, day: str) -> set[int]:
    """Distinct processes with at least one crossing; drop those whose first crossing is in 04-11 window."""
    out = set()
    for p, evs in cr.items():
        if not evs:
            continue
        first_t = evs[0][1]
        if day == "2018-04-11" and win0411 is not None and win0411[0] <= first_t <= win0411[1]:
            continue
        out.add(p)
    return out


def alerted_procs_raw(cr: dict[int, list]) -> set[int]:
    return {int(p) for p, evs in cr.items() if evs}


def alerted_procs_in_span(cr: dict[int, list], t0: int, t1: int) -> set[int]:
    out = set()
    for p, evs in cr.items():
        if any(t0 <= int(t) <= t1 for _i, t in evs):
            out.add(int(p))
    return out
