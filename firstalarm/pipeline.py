"""Val / test under PROTOCOL_v9. Streams/lineage/GT read from v8 only."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from firstalarm.alerts import alerted_procs_day, crossings
from firstalarm.calibrate import c1_ratios, calib_from_stat, select_pair, who_set
from firstalarm.config import (
    ART_ROOT,
    ATTACK_DATES,
    BUDGETS,
    PAIRS,
    TABLE_BUDGETS,
    TEST_DATES,
    V8_ART,
    VAL_DATES,
    WATCH_PROG,
    pair_tag,
)
from firstalarm.evaluate import d4_fp_split, daily_B, eval_attack, eval_d4
from firstalarm.groundtruth import GroundTruth, adjacency, forward_taint, load_groundtruth, mi_indices
from firstalarm.lineage import Lineage, load_lineage
from firstalarm.rent import Priors, build_priors, cap_q99, delta_on_stream
from firstalarm.rules import Pass, run_d2, run_d3
from firstalarm.stream import EventStream, load_stream, stream_exists
from firstalarm.timeutil import ns_to_datetime_us


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, allow_nan=True, default=_json_default), encoding="utf-8")


def _json_default(o):
    if isinstance(o, (np.floating,)):
        x = float(o)
        return None if not np.isfinite(x) else x
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o))


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_v8_streams(dataset: str, seed: int) -> None:
    missing = []
    for split, days in (("val", (VAL_DATES[dataset],)), ("test", TEST_DATES[dataset])):
        for day in days:
            if not stream_exists(dataset, seed, split, day):
                missing.append(f"{split}_{day}")
    if missing:
        raise FileNotFoundError(f"v8 streams missing {dataset} seed{seed}: {missing}")


def _priors_and_cap(val: EventStream, prior: str) -> tuple[Priors, float | None, float]:
    pr = build_priors(val, prior)
    dlt = delta_on_stream(val, pr)
    c, mass = cap_q99(val, dlt)
    pr.cap_c = c
    pr.clip_mass = mass
    return pr, c, mass


def val_seed(dataset: str, seed: int) -> dict:
    print(f"[val] {dataset} seed{seed} start", flush=True)
    assert_v8_streams(dataset, seed)
    lin = load_lineage(dataset)
    val = load_stream(dataset, seed, "val", VAL_DATES[dataset])
    h1 = calib_from_stat(val, val.s)
    out = {
        "dataset": dataset,
        "seed": seed,
        "h1": {str(k): v for k, v in h1.items()},
        "pairs": {},
        "who_d1": who_set(val, val.s, val.kind),
    }
    prior_cache = {}
    for cap, prior in PAIRS:
        if prior not in prior_cache:
            pr0, c0, mass0 = _priors_and_cap(val, prior)
            dlt = delta_on_stream(val, pr0)
            prior_cache[prior] = (pr0, c0, mass0, dlt)
        pr, c, mass, dlt = prior_cache[prior]
        cap_c = None if cap == "none" else c
        p2 = run_d2(val, pr, cap_c, lin, delta=dlt, rearm="below")
        p3 = run_d3(val, pr, cap_c, lin, True, delta=dlt, rearm="below")
        h2 = calib_from_stat(val, p2.W)
        h3 = calib_from_stat(val, p3.W)
        watch = _watch_rows(val, p3, h3, "below")
        out["pairs"][pair_tag(cap, prior)] = {
            "cap_c": None if cap_c is None else float(c),
            "clip_mass": float(mass),
            "h2": {str(k): v for k, v in h2.items()},
            "h3": {str(k): v for k, v in h3.items()},
            "c1": c1_ratios(h1, h2, h3, 2),
            "who_d2": who_set(val, p2.W, val.kind, p2.pred, p2.pred_kind),
            "who_d3": who_set(val, p3.W, val.kind, p3.pred, p3.pred_kind),
            "watch": watch,
        }
        del p2, p3
    path = ART_ROOT / dataset / f"seed{seed}" / "calib" / "val.json"
    _dump(path, out)
    print(f"[val] {dataset} seed{seed} done", flush=True)
    return out


def _watch_one(es: EventStream, p3: Pass, h: float, rearm: str) -> dict:
    watch = WATCH_PROG[es.dataset]
    kinds = {int(es.proc[i]): str(es.kind[i]) for i in range(es.n)}
    procs = {p for p, k in kinds.items() if k == watch}
    cr = _cr_mem(es, p3, float(h), False, rearm)
    return {"n_proc_kind": len(procs), "n_flagged": len(procs & set(cr.keys()))}


def _watch_rows(es: EventStream, p3: Pass, h3: dict, rearm: str) -> dict:
    return {str(b): _watch_one(es, p3, float(h3[int(b)]), rearm) for b in TABLE_BUDGETS}


def _first_ge(es: EventStream, W: np.ndarray, proc: int, h: float) -> str:
    for i in range(es.n):
        if int(es.proc[i]) == proc and float(W[i]) >= h:
            return ns_to_datetime_us(int(es.t[i]))
    return "none"


def _window_extrema(es: EventStream, W: np.ndarray, proc: int, t0: int, t1: int):
    lo = hi = None
    for i in range(es.n):
        t = int(es.t[i])
        if t < t0:
            continue
        if t > t1:
            break
        if int(es.proc[i]) != proc:
            continue
        v = float(W[i])
        lo = v if lo is None else min(lo, v)
        hi = v if hi is None else max(hi, v)
    return lo, hi


def _standing_attack(es: EventStream, p3: Pass, h3: float, rearm: str, attack, cr: dict) -> dict:
    from firstalarm.alerts import stat_at_t0

    rows = {}
    for p in sorted(attack.P):
        first = _first_ge(es, p3.W, p, h3)
        w0 = stat_at_t0(es, p3.W_mem, p, attack.t0)
        ratio = (w0 / h3) if h3 else None
        evs = cr.get(p, [])
        n_pre = sum(1 for _i, t in evs if t < attack.t0)
        in_win = [t for _i, t in evs if attack.t0 <= t <= attack.t1]
        first_win = ns_to_datetime_us(in_win[0]) if in_win else "none"
        lo = hi = None
        if rearm in ("reset", "fir"):
            lo, hi = _window_extrema(es, p3.W, p, attack.t0, attack.t1)
        rows[str(p)] = {
            "first_W_ge_h3": first,
            "w_over_h_t0": ratio,
            "n_alert_before_t0": n_pre,
            "first_in_window": first_win,
            "W_min": lo,
            "W_max": hi,
        }
    return rows


def _neutral_set(dataset: str, seed: int, gt: GroundTruth, lin: Lineage) -> set[int]:
    T, N = set(), set()
    for a in gt.attacks:
        es = load_stream(dataset, seed, "test", a.day)
        T |= forward_taint(es, a)
        N |= adjacency(es, a, lin)
    return T | N


def _cr_mem(es: EventStream, p: Pass, h: float, d1: bool, rearm: str) -> dict:
    if d1 or rearm == "below" or h is None:
        return crossings(es, p.W, h, d1)
    return {int(k): [(int(i), int(t)) for i, t in v] for k, v in p.alerts.items()}


def _slim(e: dict) -> dict:
    d = {
        "hit": e["hit"],
        "tstar_str": e["tstar_str"],
        "delay_t0": e["delay_t0"],
        "rho_e": e["rho_e"],
        "rho_n": e.get("rho_n"),
        "n_seen": e.get("n_seen"),
        "fp_day": e["fp_day"],
        "trig": e["trig"],
        "chain_has_M": e.get("chain_has_M"),
        "flag": e.get("flag"),
        "channel": e.get("channel"),
        "idx": e.get("idx"),
        "proc": e.get("proc"),
    }
    for k in ("fp_point", "fp_mem", "fp_both"):
        if k in e:
            d[k] = e[k]
    return d


def test_seed(dataset: str, seed: int, cap: str, prior: str, rearm: str) -> dict:
    print(f"[test] {dataset} seed{seed} cap={cap} prior={prior} rearm={rearm} start", flush=True)
    assert_v8_streams(dataset, seed)
    lin = load_lineage(dataset)
    gt = load_groundtruth(dataset)
    valj = load_val(dataset, seed)
    pair = valj["pairs"][pair_tag(cap, prior)]
    h1 = {int(k): float(v) for k, v in valj["h1"].items()}
    h2 = {int(k): float(v) for k, v in pair["h2"].items()}
    h3 = {int(k): float(v) for k, v in pair["h3"].items()}
    val = load_stream(dataset, seed, "val", VAL_DATES[dataset])
    pr, c, mass = _priors_and_cap(val, prior)
    cap_c = None if cap == "none" else c
    del val

    neu = _neutral_set(dataset, seed, gt, lin)
    attacks_out = {
        a.name: {"day": a.day, "t0": a.t0, "t1": a.t1, "P": sorted(a.P), "rows": {}}
        for a in gt.attacks
    }
    standing = {a.name: {} for a in gt.attacks}
    watch = {}
    # c2 accumulators: per b per rule per day B
    day_B = {str(b): {r: {} for r in ("D1", "D2", "D3", "D4")} for b in BUDGETS}

    import time as _time
    t_rep0 = _time.perf_counter()
    n_ev = 0
    for day in TEST_DATES[dataset]:
        es = load_stream(dataset, seed, "test", day)
        n_ev += es.n
        dlt = delta_on_stream(es, pr)
        S = es.s.astype(np.float64)
        day_atts = [a for a in gt.attacks if a.day == day]
        mis = {a.name: mi_indices(es, a) for a in day_atts}

        def _eval_b(b: int, p2: Pass, p3: Pass):
            cr2 = _cr_mem(es, p2, h2[int(b)], False, rearm)
            cr3 = _cr_mem(es, p3, h3[int(b)], False, rearm)
            cr1b = crossings(es, S, h1[int(b)], True)
            cr1_0 = crossings(es, S, h1[0], True)
            a1b = alerted_procs_day(cr1b, gt.window_0411, day) - set(gt.gt_procs)
            a2 = alerted_procs_day(cr2, gt.window_0411, day) - set(gt.gt_procs)
            a3 = alerted_procs_day(cr3, gt.window_0411, day) - set(gt.gt_procs)
            a10 = alerted_procs_day(cr1_0, gt.window_0411, day) - set(gt.gt_procs)
            d4 = a10 | a3
            day_B[str(b)]["D1"][day] = {"B": len(a1b), "Bp": len(a1b - neu)}
            day_B[str(b)]["D2"][day] = {"B": len(a2), "Bp": len(a2 - neu)}
            day_B[str(b)]["D3"][day] = {"B": len(a3), "Bp": len(a3 - neu)}
            day_B[str(b)]["D4"][day] = {"B": len(d4), "Bp": len(d4 - neu)}
            for a in day_atts:
                mi = mis[a.name]
                e1 = eval_attack(es, a, S, h1[int(b)], True, gt.gt_procs, gt.window_0411, None, mi)
                e2 = eval_attack(es, a, p2.W, h2[int(b)], False, gt.gt_procs, gt.window_0411, p2.pred, mi, cr=cr2, mem=p2.W_mem)
                e3 = eval_attack(es, a, p3.W, h3[int(b)], False, gt.gt_procs, gt.window_0411, p3.pred, mi, cr=cr3, mem=p3.W_mem)
                e4 = eval_d4(
                    es, a, S, p3.W, h1[0], h3[int(b)], gt.gt_procs, gt.window_0411, p3.pred, mi,
                    cr3=cr3, mem3=p3.W_mem,
                )
                attacks_out[a.name]["rows"][str(b)] = {
                    "D1": _slim(e1), "D2": _slim(e2), "D3": _slim(e3), "D4": _slim(e4),
                }
                if int(b) in TABLE_BUDGETS:
                    standing[a.name][str(b)] = _standing_attack(es, p3, h3[int(b)], rearm, a, cr3)
            if day not in ATTACK_DATES[dataset] and int(b) in TABLE_BUDGETS:
                watch.setdefault(day, {})[str(b)] = _watch_one(es, p3, h3[int(b)], rearm)

        if rearm == "below":
            p2 = run_d2(es, pr, cap_c, lin, delta=dlt, rearm="below")
            p3 = run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm="below")
            for b in BUDGETS:
                _eval_b(int(b), p2, p3)
            del p2, p3
        else:
            for b in BUDGETS:
                p2 = run_d2(es, pr, cap_c, lin, delta=dlt, rearm=rearm, h=h2[int(b)])
                p3 = run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm=rearm, h=h3[int(b)])
                _eval_b(int(b), p2, p3)
                del p2, p3
        del es, S, dlt

    wall = _time.perf_counter() - t_rep0
    ev_s = (n_ev / wall) if wall > 0 else 0.0

    c2 = {}
    for b in BUDGETS:
        c2[str(b)] = {}
        for rule in ("D1", "D2", "D3", "D4"):
            per = day_B[str(b)][rule]
            means = [v["B"] for v in per.values()]
            union = None  # not reconstructed; Table 1 uses mean_B
            c2[str(b)][rule] = {
                "per_day": per,
                "union_B": None,
                "union_Bp": None,
                "mean_B": float(np.mean(means)) if means else 0.0,
            }

    payload = {
        "dataset": dataset,
        "seed": seed,
        "cap": cap,
        "prior": prior,
        "rearm": rearm,
        "h1": {str(k): v for k, v in h1.items()},
        "h2": {str(k): v for k, v in h2.items()},
        "h3": {str(k): v for k, v in h3.items()},
        "c2": c2,
        "attacks": attacks_out,
        "standing": standing,
        "watch": watch,
        "timing": {"wall_s": wall, "n_events": n_ev, "events_per_s": ev_s},
    }
    path = ART_ROOT / dataset / f"seed{seed}" / "eval" / f"eval_{rearm}_{pair_tag(cap, prior)}.json"
    _dump(path, payload)
    print(f"[test] {dataset} seed{seed} rearm={rearm} done wall={wall:.2f}s ev/s={ev_s:.0f}", flush=True)
    return payload


def load_val(dataset: str, seed: int) -> dict:
    return _load(ART_ROOT / dataset / f"seed{seed}" / "calib" / "val.json")


def load_eval(dataset: str, seed: int, rearm: str, cap: str, prior: str) -> dict:
    return _load(ART_ROOT / dataset / f"seed{seed}" / "eval" / f"eval_{rearm}_{pair_tag(cap, prior)}.json")


def choose_from_vals(dataset: str, seeds) -> dict:
    per = {}
    for seed in seeds:
        v = load_val(dataset, seed)
        per[int(seed)] = {}
        for cap, prior in PAIRS:
            per[int(seed)][(cap, prior)] = v["pairs"][pair_tag(cap, prior)]["c1"]
    sel = select_pair(per)
    path = ART_ROOT / dataset / "selection.json"
    _dump(path, sel)
    return sel


def load_v8_eval(dataset: str, seed: int) -> dict:
    return _load(V8_ART / dataset / f"seed{seed}" / "eval" / "eval.json")


def regress_cadets_below(seeds, cap: str, prior: str) -> dict:
    """Compare CADETS below vs v8.2 eval.json. Stop details if unexpected diffs."""
    diffs = []
    already_fate = []
    ok_window = 0
    n_window = 0
    for seed in seeds:
        v9 = load_eval("CADETS_E3", seed, "below", cap, prior)
        v8 = load_v8_eval("CADETS_E3", seed)
        for name, att8 in v8["attacks"].items():
            att9 = v9["attacks"][name]
            for b, row8 in att8["rows"].items():
                for rule in ("D1", "D2", "D3", "D4"):
                    e8, e9 = row8[rule], att9["rows"][str(b)][rule]
                    fl = e8.get("flag")
                    if rule == "D4" and fl is None and e8.get("hit"):
                        ch = e8.get("trig")
                        d10 = att8["rows"]["0"]["D1"]
                        d3 = row8["D3"]
                        if ch == "D3":
                            fl = d3.get("flag")
                        elif ch == "D1":
                            fl = d10.get("flag") if d10.get("tstar_str") == e8.get("tstar_str") else d10.get("flag")
                        elif ch == "D1+D3":
                            fl = d10.get("flag") if d10.get("flag") == d3.get("flag") else d3.get("flag")
                    keys = ("hit", "tstar_str", "rho_e", "delay_t0", "fp_day")
                    if fl in ("window", "pre60"):
                        n_window += 1
                        mism = {k: (e8.get(k), e9.get(k)) for k in keys if e8.get(k) != e9.get(k)}
                        # float tolerance
                        drop = []
                        for k, (a, b_) in list(mism.items()):
                            if isinstance(a, float) and isinstance(b_, float) and abs(a - b_) < 1e-12:
                                drop.append(k)
                        for k in drop:
                            del mism[k]
                        if not mism:
                            ok_window += 1
                        else:
                            diffs.append({
                                "seed": seed, "attack": name, "b": b, "rule": rule,
                                "v8_flag": fl, "mismatch": mism, "v9_flag": e9.get("flag"),
                            })
                    elif fl == "already":
                        fate = "miss"
                        if e9.get("hit"):
                            ts = e9.get("tstar_str") or ""
                            fate = f"hit:{e9.get('flag')}:{ts}"
                        already_fate.append({
                            "seed": seed, "attack": name, "b": b, "rule": rule,
                            "v8_tstar": e8.get("tstar_str"), "v8_rho": e8.get("rho_e"),
                            "v9_hit": e9.get("hit"), "v9_flag": e9.get("flag"),
                            "v9_tstar": e9.get("tstar_str"), "fate": fate,
                        })
                    elif e8.get("hit") or e9.get("hit"):
                        if fl is None and not e8.get("hit") and not e9.get("hit"):
                            continue
                        if e8.get("hit") != e9.get("hit") or (e8.get("hit") and e8.get("tstar_str") != e9.get("tstar_str")):
                            diffs.append({
                                "seed": seed, "attack": name, "b": b, "rule": rule,
                                "v8_flag": fl, "v8_hit": e8.get("hit"), "v9_hit": e9.get("hit"),
                                "v8_tstar": e8.get("tstar_str"), "v9_tstar": e9.get("tstar_str"),
                                "note": "non-window/pre60/already difference",
                            })
    return {
        "ok_window": ok_window,
        "n_window": n_window,
        "n_diffs": len(diffs),
        "diffs": diffs,
        "already_fate": already_fate,
        "pass": len(diffs) == 0,
    }


def regress_theia_below(seeds, cap: str, prior: str) -> dict:
    cells = []
    n_same = 0
    n_diff = 0
    for seed in seeds:
        v9 = load_eval("THEIA_E3", seed, "below", cap, prior)
        v8 = load_v8_eval("THEIA_E3", seed)
        for name, att8 in v8["attacks"].items():
            att9 = v9["attacks"][name]
            for b, row8 in att8["rows"].items():
                for rule in ("D1", "D2", "D3", "D4"):
                    e8, e9 = row8[rule], att9["rows"][str(b)][rule]
                    same = all(e8.get(k) == e9.get(k) for k in ("hit", "tstar_str", "rho_e", "delay_t0", "fp_day"))
                    if same:
                        n_same += 1
                    else:
                        n_diff += 1
                        cells.append({
                            "seed": seed, "attack": name, "b": b, "rule": rule,
                            "v8_flag": e8.get("flag"), "v9_flag": e9.get("flag"),
                            "v8_hit": e8.get("hit"), "v9_hit": e9.get("hit"),
                            "v8_tstar": e8.get("tstar_str"), "v9_tstar": e9.get("tstar_str"),
                            "v8_rho": e8.get("rho_e"), "v9_rho": e9.get("rho_e"),
                        })
    return {"n_same": n_same, "n_diff": n_diff, "cells": cells}
