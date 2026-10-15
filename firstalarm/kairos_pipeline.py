"""Kairos / ORTHRUS-scored val/test. Writes only the current scorer art root."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from firstalarm.alerts import alerted_procs_day, crossings
from firstalarm.calibrate import c1_ratios, calib_from_stat, select_pair, who_set
from firstalarm.config import ATTACK_DATES, BUDGETS, PAIRS, TABLE_BUDGETS, TEST_DATES, VAL_DATES, pair_tag
from firstalarm.evaluate import eval_attack, eval_d4
from firstalarm.groundtruth import load_groundtruth, mi_indices
from firstalarm.kairos_align import load_kairos_stream
from firstalarm.kairos_config import DATASET, assert_write_path, spec
from firstalarm.lineage import load_lineage
from firstalarm.pipeline import (
    _cr_mem,
    _json_default,
    _neutral_set,
    _priors_and_cap,
    _slim,
    _standing_attack,
    _watch_one,
    _watch_rows,
)
from firstalarm.rent import delta_on_stream
from firstalarm.rules import Pass, run_d2, run_d3
from firstalarm.stream import EventStream


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, allow_nan=True, default=_json_default), encoding="utf-8")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _art() -> Path:
    return assert_write_path(spec().art)


def val_seed(seed: int) -> dict:
    name = spec().name
    print(f"[{name} val] seed{seed} start", flush=True)
    lin = load_lineage(DATASET)
    val = load_kairos_stream(seed, "val", VAL_DATES[DATASET])
    h1 = calib_from_stat(val, val.s)
    out = {
        "dataset": DATASET,
        "seed": seed,
        "scorer": name,
        "h1": {str(k): v for k, v in h1.items()},
        "pairs": {},
        "who_d1": who_set(val, val.s, val.kind),
        "val_max_loss": float(np.max(val.s)),
        "val_max_proc_loss": float(np.max(val.s[val.proc_type == 0])) if np.any(val.proc_type == 0) else float(np.max(val.s)),
        "n_flagged_d1": {str(b): len(crossings(val, val.s, float(h1[int(b)]), True)) for b in BUDGETS},
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
        out["pairs"][pair_tag(cap, prior)] = {
            "cap_c": None if cap_c is None else float(c),
            "clip_mass": float(mass),
            "h2": {str(k): v for k, v in h2.items()},
            "h3": {str(k): v for k, v in h3.items()},
            "c1": c1_ratios(h1, h2, h3, 2),
            "who_d2": who_set(val, p2.W, val.kind, p2.pred, p2.pred_kind),
            "who_d3": who_set(val, p3.W, val.kind, p3.pred, p3.pred_kind),
            "watch": _watch_rows(val, p3, h3, "below"),
        }
        del p2, p3
    path = _art() / DATASET / f"seed{seed}" / "calib" / "val.json"
    _dump(path, out)
    print(f"[{name} val] seed{seed} done", flush=True)
    return out


def test_seed(seed: int, cap: str, prior: str, rearm: str = "reset") -> dict:
    name = spec().name
    print(f"[{name} test] seed{seed} cap={cap} prior={prior} rearm={rearm} start", flush=True)
    lin = load_lineage(DATASET)
    gt = load_groundtruth(DATASET)
    valj = load_val(seed)
    pair = valj["pairs"][pair_tag(cap, prior)]
    h1 = {int(k): float(v) for k, v in valj["h1"].items()}
    h2 = {int(k): float(v) for k, v in pair["h2"].items()}
    h3 = {int(k): float(v) for k, v in pair["h3"].items()}
    val = load_kairos_stream(seed, "val", VAL_DATES[DATASET])
    pr, c, mass = _priors_and_cap(val, prior)
    cap_c = None if cap == "none" else c
    del val

    neu = _neutral_set(DATASET, seed, gt, lin)
    attacks_out = {a.name: {"day": a.day, "t0": a.t0, "t1": a.t1, "P": sorted(a.P), "rows": {}} for a in gt.attacks}
    standing = {a.name: {} for a in gt.attacks}
    watch = {}
    day_B = {str(b): {r: {} for r in ("D1", "D2", "D3", "D4")} for b in BUDGETS}

    t_rep0 = time.perf_counter()
    n_ev = 0
    for day in TEST_DATES[DATASET]:
        es = load_kairos_stream(seed, "test", day)
        n_ev += es.n
        dlt = delta_on_stream(es, pr)
        S = es.s.astype(np.float64)
        day_atts = [a for a in gt.attacks if a.day == day]
        mis = {a.name: mi_indices(es, a) for a in day_atts}

        def _eval_b(b: int, p2: Pass, p3: Pass, es=es, S=S, dlt=dlt, day=day, day_atts=day_atts, mis=mis):
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
                e4 = eval_d4(es, a, S, p3.W, h1[0], h3[int(b)], gt.gt_procs, gt.window_0411, p3.pred, mi, cr3=cr3, mem3=p3.W_mem)
                attacks_out[a.name]["rows"][str(b)] = {
                    "D1": _slim(e1), "D2": _slim(e2), "D3": _slim(e3), "D4": _slim(e4),
                }
                if int(b) in TABLE_BUDGETS:
                    standing[a.name][str(b)] = _standing_attack(es, p3, h3[int(b)], rearm, a, cr3)
            if day not in ATTACK_DATES[DATASET] and int(b) in TABLE_BUDGETS:
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

    wall = time.perf_counter() - t_rep0
    ev_s = (n_ev / wall) if wall > 0 else 0.0
    c2 = {}
    for b in BUDGETS:
        c2[str(b)] = {}
        for rule in ("D1", "D2", "D3", "D4"):
            per = day_B[str(b)][rule]
            means = [v["B"] for v in per.values()]
            c2[str(b)][rule] = {
                "per_day": per,
                "union_B": None,
                "union_Bp": None,
                "mean_B": float(np.mean(means)) if means else 0.0,
            }
    payload = {
        "dataset": DATASET,
        "seed": seed,
        "scorer": name,
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
    path = _art() / DATASET / f"seed{seed}" / "eval" / f"eval_{rearm}_{pair_tag(cap, prior)}.json"
    _dump(path, payload)
    print(f"[{name} test] seed{seed} done wall={wall:.2f}s ev/s={ev_s:.0f}", flush=True)
    return payload


def load_val(seed: int) -> dict:
    return _load(spec().art / DATASET / f"seed{seed}" / "calib" / "val.json")


def load_eval(seed: int, rearm: str, cap: str, prior: str) -> dict:
    return _load(spec().art / DATASET / f"seed{seed}" / "eval" / f"eval_{rearm}_{pair_tag(cap, prior)}.json")


def choose_from_vals(seeds) -> dict:
    per = {}
    for seed in seeds:
        v = load_val(seed)
        per[int(seed)] = {}
        for cap, prior in PAIRS:
            per[int(seed)][(cap, prior)] = v["pairs"][pair_tag(cap, prior)]["c1"]
    sel = select_pair(per)
    _dump(_art() / DATASET / "selection.json", sel)
    return sel
