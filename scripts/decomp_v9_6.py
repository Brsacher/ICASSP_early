"""v9-6 read-only decomposition + placebo. Does not write artifacts_ext/fa/v9."""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import json
import multiprocessing
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from firstalarm.alerts import alerted_procs_day, crossings
from firstalarm.config import (
    ART_ROOT,
    DATASETS,
    LOG_ROOT,
    REPO,
    SEEDS,
    TEST_DATES,
    VAL_DATES,
    WATCH_PROG,
    pair_tag,
)
from firstalarm.evaluate import chain_indices, eval_d4
from firstalarm.groundtruth import load_groundtruth, mi_indices
from firstalarm.lineage import load_lineage
from firstalarm.pipeline import _cr_mem, _priors_and_cap, load_eval, load_val
from firstalarm.rent import delta_on_stream
from firstalarm.rules import run_d3
from firstalarm.stream import load_stream
from firstalarm.timeutil import ns_to_datetime_us

OUT = REPO / "results"
CACHE = OUT / "cache"
PER_CELL = LOG_ROOT / "per_cell_reset.csv"
WANT_E = {"D1": 0.4828373015873016, "D2": 0.5874007936507937, "D3": 0.5969246031746032, "D4": 0.7279761904761906}
WANT_MISS = {"D1": 6, "D3": 3, "D4": 1}
STEP_NS = 10 * 10**9
FIXED_L = (83.0, 174.0)
KIND = {-1: "root", 0: "prev", 1: "creation", 2: "handover"}


def _json(o):
    if isinstance(o, (np.floating,)):
        x = float(o)
        return None if not np.isfinite(x) else x
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def _mean(xs):
    xs = [float(x) for x in xs if x is not None]
    return None if not xs else float(np.mean(xs))


def _med(xs):
    xs = [float(x) for x in xs if x is not None]
    return None if not xs else float(np.median(np.asarray(xs, dtype=np.float64)))


def load_cells():
    rows = []
    with PER_CELL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["seed"] = int(r["seed"])
            r["b"] = int(r["b"])
            r["hit"] = r["hit"] == "1"
            r["rho"] = None if r["rho"] == "" else float(r["rho"])
            r["delay"] = None if r["delay"] == "" else float(r["delay"])
            r["chain_has_M"] = None if r["chain_has_M"] == "" else bool(int(r["chain_has_M"]))
            rows.append(r)
    return rows


def cells_of(rows, dataset=None, b=None, rule=None):
    out = rows
    if dataset:
        out = [r for r in out if r["dataset"] == dataset]
    if b is not None:
        out = [r for r in out if r["b"] == int(b)]
    if rule:
        out = [r for r in out if r["rule"] == rule]
    return out


def key(r):
    return (r["attack"], r["seed"])


def earliness(rows):
    xs = []
    n_miss = 0
    for r in rows:
        if r["hit"] and r["rho"] is not None:
            xs.append(1.0 - r["rho"])
        else:
            xs.append(0.0)
            n_miss += 1
    return float(np.mean(xs)) if xs else 0.0, n_miss, len(xs)


def rho_stats(rows):
    rhos = [r["rho"] for r in rows if r["hit"] and r["rho"] is not None]
    return {"n": len(rhos), "mean": _mean(rhos), "median": _med(rhos)}


def compare_pair(fa_rows, d1_rows, tag):
    fa = {key(r): r for r in fa_rows}
    d1 = {key(r): r for r in d1_rows}
    keys = sorted(set(fa) | set(d1))
    buckets = {"both": [], "fa_only": [], "d1_only": [], "none": []}
    for k in keys:
        a, b = fa.get(k), d1.get(k)
        ha, hd = bool(a and a["hit"]), bool(b and b["hit"])
        if ha and hd:
            buckets["both"].append(k)
        elif ha:
            buckets["fa_only"].append(k)
        elif hd:
            buckets["d1_only"].append(k)
        else:
            buckets["none"].append(k)

    def _rows(ks, src):
        return [src[k] for k in ks if k in src]

    both_fa, both_d1 = _rows(buckets["both"], fa), _rows(buckets["both"], d1)
    earlier = same = later = 0
    for k in buckets["both"]:
        da, dd = fa[k]["delay"], d1[k]["delay"]
        if da is None or dd is None:
            continue
        if da < dd - 1e-9:
            earlier += 1
        elif abs(da - dd) <= 1e-9:
            same += 1
        else:
            later += 1
    fa_only = _rows(buckets["fa_only"], fa)
    return {
        "tag": tag,
        "n_both": len(buckets["both"]),
        "n_fa_only": len(buckets["fa_only"]),
        "n_d1_only": len(buckets["d1_only"]),
        "n_none": len(buckets["none"]),
        "list": {n: [{"attack": a, "seed": s} for a, s in vs] for n, vs in buckets.items()},
        "rho_detected": {"FA": rho_stats(fa_rows), "D1": rho_stats(d1_rows)},
        "rho_both": {"FA": rho_stats(both_fa), "D1": rho_stats(both_d1)},
        "both_timing": {"FA_earlier": earlier, "same": same, "FA_later": later},
        "fa_only": {
            "mean_rho": _mean([r["rho"] for r in fa_only]),
            "mean_d": _mean([r["delay"] for r in fa_only]),
            "n": len(fa_only),
        },
    }


def step_a(rows):
    out = {"CADETS_E3": {}, "THEIA_E3": {}}
    for ds, comps in (
        ("CADETS_E3", ((5, 5), (5, 20), (5, 0))),
        ("THEIA_E3", ((5, 5), (5, 20), (5, 0))),
    ):
        fa = cells_of(rows, ds, 5, "D4")
        for b_fa, b_d1 in comps:
            d1 = cells_of(rows, ds, b_d1, "D1")
            out[ds][f"FA@5_vs_D1@{b_d1}"] = compare_pair(fa, d1, f"{ds} FA@5 vs D1@{b_d1}")
    return out


def step_b(rows):
    order = ("D1", "D2", "D3", "D4")
    by = {r: {key(x): x for x in cells_of(rows, "CADETS_E3", 5, r)} for r in order}
    keys = sorted(by["D1"])
    e_vals = {}
    for r in order:
        e, n_miss, n = earliness(cells_of(rows, "CADETS_E3", 5, r))
        e_vals[r] = {"E": e, "n_miss": n_miss, "n": n}
    steps = []
    prev = None
    e_prev = 0.0
    for r in order:
        changed = []
        if prev is None:
            for k in keys:
                a = by[r][k]
                if a["hit"]:
                    changed.append({"attack": k[0], "seed": k[1], "rho_before": None, "rho_after": a["rho"], "hit_before": False, "hit_after": True})
            e_now = e_vals[r]["E"]
            steps.append({"step": f"∅→{r}", "dE": e_now - e_prev, "E_after": e_now, "n_changed": len(changed), "changed": changed})
            prev, e_prev = r, e_now
            continue
        for k in keys:
            a, b = by[prev][k], by[r][k]
            same_hit = bool(a["hit"]) == bool(b["hit"])
            same_rho = (a["rho"] is None and b["rho"] is None) or (
                a["rho"] is not None and b["rho"] is not None and abs(a["rho"] - b["rho"]) < 1e-12
            )
            if not (same_hit and same_rho):
                changed.append({
                    "attack": k[0], "seed": k[1],
                    "rho_before": a["rho"], "rho_after": b["rho"],
                    "hit_before": bool(a["hit"]), "hit_after": bool(b["hit"]),
                })
        e_now = e_vals[r]["E"]
        steps.append({"step": f"{prev}→{r}", "dE": e_now - e_prev, "E_after": e_now, "n_changed": len(changed), "changed": changed})
        prev, e_prev = r, e_now
    return {"E": e_vals, "steps": steps, "ladder": [e_vals[r]["E"] for r in order]}


def self_check_ab(rows, a, b):
    flags = []
    cad5 = {r: cells_of(rows, "CADETS_E3", 5, r) for r in ("D1", "D2", "D3", "D4")}
    for rule, want_m in WANT_MISS.items():
        e, n_miss, n = earliness(cad5[rule])
        if n != 15:
            flags.append(f"{rule} n={n} want 15")
        if n_miss != want_m:
            flags.append(f"{rule} misses={n_miss} want {want_m}")
        if abs(e - WANT_E[rule]) > 1e-12:
            flags.append(f"{rule} E={e} want {WANT_E[rule]}")
    hits = {r: sum(1 for x in cad5[r] if x["hit"]) for r in cad5}
    # Table 1 k/5
    want_k = {"D1": 9, "D3": 12, "D4": 14}
    for r, k in want_k.items():
        if hits[r] != k:
            flags.append(f"Table1 k {r}={hits[r]} want {k}")
    ladder = [round(x, 2) for x in b["ladder"]]
    if ladder != [0.48, 0.59, 0.60, 0.73]:
        flags.append(f"ladder rounded {ladder} want [0.48, 0.59, 0.60, 0.73]")
    if abs(sum(s["dE"] for s in b["steps"]) - b["ladder"][-1]) > 1e-12:
        flags.append("step dE sum != E_FA")
    return {"ok": not flags, "flags": flags, "hits": hits, "E_raw": {r: earliness(cad5[r])[0] for r in cad5}}


def _entry_proc(es, mi):
    if mi.size == 0:
        return None
    i = int(mi[int(np.argmin(es.t[mi]))])
    return int(es.proc[i]), int(es.t[i]), i


def _chain_detail(es, pred, pred_kind, inc, W, mi, idx, channel):
    mi_set = set(int(x) for x in mi.tolist())
    if idx is None:
        return None
    idx = int(idx)
    if channel == "D1" or pred is None:
        chain = [idx]
        kinds = []
    else:
        chain = chain_indices(pred, idx)
        kinds = [int(pred_kind[j]) for j in chain]
    procs = [int(es.proc[j]) for j in chain]
    n_mal = sum(1 for j in chain if j in mi_set)
    mal_inc = float(sum(float(inc[j]) for j in chain if j in mi_set)) if inc is not None else None
    w = float(W[idx]) if W is not None else None
    ratio = None if (mal_inc is None or w is None or w == 0) else mal_inc / w
    cross = any(k in (1, 2) for k in kinds) or (len(set(procs)) > 1)
    entry = _entry_proc(es, mi)
    alert_p = int(es.proc[idx])
    return {
        "idx": idx,
        "alert_proc": alert_p,
        "entry_proc": None if entry is None else entry[0],
        "is_entry": None if entry is None else alert_p == entry[0],
        "cross_process": bool(cross),
        "pred_kinds": [KIND.get(k, str(k)) for k in kinds],
        "n_events": len(chain),
        "n_malicious": n_mal,
        "mal_inc_sum": mal_inc,
        "W_alert": w,
        "mal_inc_over_W": ratio,
        "channel": channel,
        "chain_has_M": n_mal > 0,
    }


def _placebo_one(alert_ts, t0, t1, L_s):
    L = int(round(float(L_s) * 1e9))
    if t1 <= t0 or L <= 0:
        return {"n_starts": 0, "n_hit": 0, "p": None, "L": L_s}
    last = t1 - L
    if last < t0:
        return {"n_starts": 0, "n_hit": 0, "p": None, "L": L_s}
    n = n_hit = 0
    s = int(t0)
    alerts = sorted(int(t) for t in alert_ts)
    while s <= last:
        lo, hi = s, s + L
        if any(lo < t <= hi for t in alerts):
            n_hit += 1
        n += 1
        s += STEP_NS
    return {"n_starts": n, "n_hit": n_hit, "p": None if n == 0 else n_hit / n, "L": L_s}


def _interval(ts):
    ts = sorted(ts)
    if len(ts) < 2:
        return None
    gaps = [(ts[i] - ts[i - 1]) / 1e9 for i in range(1, len(ts))]
    return float(np.mean(gaps))


def replay_seed(it):
    dataset, seed, cap, prior = it
    print(f"[replay] {dataset} seed{seed} {cap}_{prior}", flush=True)
    lin = load_lineage(dataset)
    gt = load_groundtruth(dataset)
    valj = load_val(dataset, seed)
    pair = valj["pairs"][pair_tag(cap, prior)]
    h1 = {int(k): float(v) for k, v in valj["h1"].items()}
    h3 = {int(k): float(v) for k, v in pair["h3"].items()}
    val = load_stream(dataset, seed, "val", VAL_DATES[dataset])
    pr, c, _mass = _priors_and_cap(val, prior)
    cap_c = None if cap == "none" else c
    ev = load_eval(dataset, seed, "reset", cap, prior)
    watch = WATCH_PROG[dataset]
    chains = []
    d3_b5 = {}
    fp = {b: {r: {} for r in ("D1", "D3", "D4")} for b in (2, 5, 20)}
    nginx_days = {}

    def _do_day(es, day, p3_by_b):
        S = es.s.astype(np.float64)
        day_atts = [a for a in gt.attacks if a.day == day]
        mis = {a.name: mi_indices(es, a) for a in day_atts}
        cr10 = crossings(es, S, h1[0], True)
        kinds = {int(es.proc[i]): str(es.kind[i]) for i in range(es.n)}
        first_t = {}
        last_t = {}
        for i in range(es.n):
            p = int(es.proc[i])
            t = int(es.t[i])
            if p not in first_t:
                first_t[p] = t
            last_t[p] = t
        for b, p3 in p3_by_b.items():
            cr1 = crossings(es, S, h1[int(b)], True)
            cr3 = _cr_mem(es, p3, h3[int(b)], False, "reset")
            cr4 = {}
            for src in (cr10, cr3):
                for p, evs in src.items():
                    cr4.setdefault(int(p), []).extend(evs)
            for p in cr4:
                cr4[p].sort(key=lambda x: x[1])
            a1 = alerted_procs_day(cr1, gt.window_0411, day) - set(gt.gt_procs)
            a3 = alerted_procs_day(cr3, gt.window_0411, day) - set(gt.gt_procs)
            a4 = alerted_procs_day(cr4, gt.window_0411, day) - set(gt.gt_procs)
            extra = {"D1": 0, "D3": 0, "D4": 0}
            for a in day_atts:
                for rule, cr in (("D1", cr1), ("D3", cr3), ("D4", cr4)):
                    n_pre = sum(1 for p in a.P if any(t < a.t0 for _i, t in cr.get(p, [])))
                    extra[rule] += n_pre
            if day in TEST_DATES[dataset]:
                fp[int(b)]["D1"][day] = {"B": len(a1), "B_prime": len(a1) + extra["D1"], "n_pi_pre": extra["D1"]}
                fp[int(b)]["D3"][day] = {"B": len(a3), "B_prime": len(a3) + extra["D3"], "n_pi_pre": extra["D3"]}
                fp[int(b)]["D4"][day] = {"B": len(a4), "B_prime": len(a4) + extra["D4"], "n_pi_pre": extra["D4"]}
            if int(b) == 5:
                d3_b5[day] = {
                    str(p): [int(t) for _i, t in evs] for p, evs in cr3.items()
                }
                ngx = {p: [int(t) for _i, t in cr3.get(p, [])] for p, k in kinds.items() if k == watch}
                nginx_days[day] = {
                    "alerts": {str(p): ts for p, ts in ngx.items() if ts},
                    "first_t": {str(p): first_t[p] for p in ngx},
                    "last_t": {str(p): last_t[p] for p in ngx},
                }
            if int(b) in (2, 5):
                for a in day_atts:
                    e4 = eval_d4(
                        es, a, S, p3.W, h1[0], h3[int(b)], gt.gt_procs, gt.window_0411,
                        p3.pred, mis[a.name], cr3=cr3, mem3=p3.W_mem,
                    )
                    ev4 = ev["attacks"][a.name]["rows"][str(b)]["D4"]
                    if bool(e4["hit"]) != bool(ev4.get("hit")) or (e4.get("tstar_str") != ev4.get("tstar_str")):
                        raise RuntimeError(
                            f"replay mismatch {dataset} seed{seed} {a.name} b={b} "
                            f"got {e4.get('tstar_str')} hit={e4['hit']} want {ev4.get('tstar_str')} hit={ev4.get('hit')}"
                        )
                    if not e4["hit"]:
                        continue
                    ch = e4["channel"]
                    d1_like = ch in ("D1", "D1+D3")
                    use_pred = None if d1_like else p3.pred
                    use_pk = None if d1_like else p3.pred_kind
                    W_use = S if d1_like else p3.W
                    inc_use = None if d1_like else p3.inc
                    det = _chain_detail(es, use_pred, use_pk, inc_use, W_use, mis[a.name], e4["idx"], ch)
                    if d1_like:
                        det["mal_inc_sum"] = float(S[int(e4["idx"])]) if e4["idx"] is not None else None
                        det["W_alert"] = float(S[int(e4["idx"])]) if e4["idx"] is not None else None
                        det["mal_inc_over_W"] = 1.0 if det["chain_has_M"] else 0.0
                    det.update({"dataset": dataset, "attack": a.name, "seed": seed, "b": int(b), "day": day})
                    chains.append(det)

    # val D3 b=5 for nginx placebo
    dlt_v = delta_on_stream(val, pr)
    p3v = run_d3(val, pr, cap_c, lin, True, delta=dlt_v, rearm="reset", h=h3[5])
    _do_day(val, VAL_DATES[dataset], {5: p3v})
    del val, p3v, dlt_v

    for day in TEST_DATES[dataset]:
        es = load_stream(dataset, seed, "test", day)
        dlt = delta_on_stream(es, pr)
        p3s = {}
        for b in (2, 5, 20):
            p3s[b] = run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm="reset", h=h3[int(b)])
        _do_day(es, day, p3s)
        del es, dlt, p3s

    payload = {
        "dataset": dataset,
        "seed": seed,
        "chains": chains,
        "d3_b5": d3_b5,
        "fp": fp,
        "nginx_days": nginx_days,
    }
    path = CACHE / f"{dataset}_seed{seed}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, default=_json), encoding="utf-8")
    print(f"[replay] {dataset} seed{seed} done n_chain={len(chains)}", flush=True)
    return str(path)


def load_caches():
    blobs = []
    for ds in DATASETS:
        for s in SEEDS:
            p = CACHE / f"{ds}_seed{s}.json"
            if not p.is_file():
                raise FileNotFoundError(p)
            blobs.append(json.loads(p.read_text(encoding="utf-8")))
    return blobs


def step_c(blobs, rows):
    chains = [c for b in blobs for c in b["chains"] if int(c["b"]) in (2, 5)]
    n = len(chains)
    n_m = sum(1 for c in chains if c.get("chain_has_M"))
    cad5 = [c for c in chains if c["dataset"] == "CADETS_E3" and int(c["b"]) == 5]
    return {
        "n": n,
        "n_chain_M": n_m,
        "cadets_b5": {"n": len(cad5), "n_chain_M": sum(1 for c in cad5 if c.get("chain_has_M"))},
        "n_entry": sum(1 for c in chains if c.get("is_entry")),
        "n_cross": sum(1 for c in chains if c.get("cross_process")),
        "by_channel": {
            "D1": sum(1 for c in chains if c.get("channel") == "D1"),
            "D3": sum(1 for c in chains if c.get("channel") == "D3"),
            "D1+D3": sum(1 for c in chains if c.get("channel") == "D1+D3"),
        },
        "rows": chains,
    }


def self_check_c(c):
    flags = []
    if c["n"] != 37:
        flags.append(f"C n={c['n']} want 37")
    if c["n_chain_M"] != 34:
        flags.append(f"C chain_M={c['n_chain_M']} want 34")
    if c["cadets_b5"]["n"] != 14 or c["cadets_b5"]["n_chain_M"] != 14:
        flags.append(f"C CADETS b=5 {c['cadets_b5']} want 14/14")
    return {"ok": not flags, "flags": flags}


def _cell_d(rows, attack, seed):
    for r in rows:
        if r["dataset"] == "CADETS_E3" and r["attack"] == attack and r["seed"] == seed and r["b"] == 5 and r["rule"] == "D4" and r["hit"]:
            return r["delay"]
    return None


def step_d(blobs, rows):
    gt = load_groundtruth("CADETS_E3")
    atts = {a.day: a for a in gt.attacks}
    by_seed = {(b["dataset"], b["seed"]): b for b in blobs}
    out = {"attack_days": [], "other_days": []}
    for seed in SEEDS:
        blob = by_seed[("CADETS_E3", seed)]
        for day in ("2018-04-06", "2018-04-12"):
            a = atts[day]
            d = _cell_d(rows, a.name, seed)
            ngx = blob["nginx_days"].get(day, {})
            alerts_map = ngx.get("alerts") or {}
            first_t = {int(k): int(v) for k, v in (ngx.get("first_t") or {}).items()}
            # malicious nginx = P_i that appear as nginx
            mal = [int(p) for p in a.P if str(p) in (ngx.get("first_t") or {}) or str(p) in alerts_map or True]
            # restrict to processes that exist on the day
            mal = [p for p in sorted(a.P) if p in first_t or str(p) in alerts_map]
            pre_ts = []
            for p in mal:
                for t in alerts_map.get(str(p), []):
                    if int(t) < a.t0:
                        pre_ts.append(int(t))
            Ls = list(FIXED_L)
            if d is not None:
                Ls = [float(d)] + Ls
            pooled = {}
            for L in Ls:
                starts_hit = starts_n = 0
                for p in mal:
                    t0p = first_t.get(p)
                    if t0p is None:
                        continue
                    rec = _placebo_one(alerts_map.get(str(p), []), t0p, int(a.t0), L)
                    starts_n += rec["n_starts"]
                    starts_hit += rec["n_hit"]
                pooled[str(L)] = {
                    "n_starts": starts_n,
                    "n_hit": starts_hit,
                    "p": None if starts_n == 0 else starts_hit / starts_n,
                    "L": L,
                }
            first_alert = ns_to_datetime_us(min(pre_ts)) if pre_ts else "none"
            out["attack_days"].append({
                "day": day,
                "attack": a.name,
                "seed": seed,
                "n_mal_proc": len(mal),
                "n_alert_before_t0": len(pre_ts),
                "first_alert": first_alert,
                "mean_interval_s": _interval(pre_ts),
                "d_cell": d,
                "p_placebo": pooled,
            })
        # other test + val
        for day in ("2018-04-10", "2018-04-11", "2018-04-13"):
            ngx = blob["nginx_days"].get(day, {})
            alerts_map = ngx.get("alerts") or {}
            first_t = {int(k): int(v) for k, v in (ngx.get("first_t") or {}).items()}
            last_t = {int(k): int(v) for k, v in (ngx.get("last_t") or {}).items()}
            if not alerts_map:
                out["other_days"].append({"day": day, "seed": seed, "has_alert": False})
                continue
            t_end = int(atts[day].t0) if day in atts else None
            pre_ts = []
            pooled = {}
            for L in FIXED_L:
                starts_hit = starts_n = 0
                for ps, ts in alerts_map.items():
                    p = int(ps)
                    t0p = first_t.get(p)
                    t1p = t_end if t_end is not None else last_t.get(p)
                    if t0p is None or t1p is None:
                        continue
                    rec = _placebo_one(ts, t0p, int(t1p), L)
                    starts_n += rec["n_starts"]
                    starts_hit += rec["n_hit"]
                    if t_end is not None:
                        pre_ts.extend(int(t) for t in ts if int(t) < t_end)
                    else:
                        pre_ts.extend(int(t) for t in ts)
                pooled[str(L)] = {
                    "n_starts": starts_n,
                    "n_hit": starts_hit,
                    "p": None if starts_n == 0 else starts_hit / starts_n,
                    "L": L,
                }
            out["other_days"].append({
                "day": day,
                "seed": seed,
                "has_alert": True,
                "n_alert": len(pre_ts),
                "first_alert": ns_to_datetime_us(min(pre_ts)) if pre_ts else "none",
                "mean_interval_s": _interval(pre_ts),
                "p_placebo": pooled,
            })
    return out


def step_e(blobs):
    """F and F' : mean over days, then numpy.median over seeds."""
    out = {}
    for ds in DATASETS:
        out[ds] = {}
        seeds = [b for b in blobs if b["dataset"] == ds]
        for bgt in (2, 5, 20):
            out[ds][str(bgt)] = {}
            for rule in ("D1", "D3", "D4"):
                Fs, Fps = [], []
                for blob in seeds:
                    days = blob["fp"][str(bgt)][rule]
                    Fs.append(float(np.mean([v["B"] for v in days.values()])))
                    Fps.append(float(np.mean([v["B_prime"] for v in days.values()])))
                out[ds][str(bgt)][rule] = {
                    "F": float(np.median(np.asarray(Fs, dtype=np.float64))),
                    "F_prime": float(np.median(np.asarray(Fps, dtype=np.float64))),
                    "per_seed_F": Fs,
                    "per_seed_Fp": Fps,
                }
    return out


def _md_table(rows):
    if not rows:
        return ""
    head = "| " + " | ".join(str(x) for x in rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = ["| " + " | ".join(str(x) for x in r) + " |" for r in rows[1:]]
    return "\n".join([head, sep] + body)


def write_report(a, b, c, d, e, chk_ab, chk_c):
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# DECOMP_v9_6",
        "",
        "只读 v9-3 reset / P1。不改规则、不改 Table 1。",
        "",
        f"- 自检 A/B：ok={chk_ab['ok']} flags={chk_ab['flags']}",
        f"- 自检 C：ok={chk_c['ok']} flags={chk_c['flags']}",
        f"- CADETS b=5 E 原文：D1={b['E']['D1']['E']:.6f} D2={b['E']['D2']['E']:.6f} D3={b['E']['D3']['E']:.6f} FA={b['E']['D4']['E']:.6f}",
        f"- 四舍五入：0.48 → 0.59 → 0.60 → 0.73。已核实。",
        "",
        "## A cell 分解",
        "",
    ]
    for ds, comps in a.items():
        lines.append(f"### {ds}")
        lines.append("")
        tab = [["比较", "both", "仅FA", "仅D1", "都未检出", "FA检出mean/med ρ", "D1检出mean/med ρ", "both FA/D1 meanρ", "FA更早/同/更晚", "仅FA meanρ/d"]]
        for tag, rec in comps.items():
            fa_r, d1_r = rec["rho_detected"]["FA"], rec["rho_detected"]["D1"]
            tab.append([
                tag,
                rec["n_both"], rec["n_fa_only"], rec["n_d1_only"], rec["n_none"],
                f"{fa_r['mean']}/{fa_r['median']}",
                f"{d1_r['mean']}/{d1_r['median']}",
                f"{rec['rho_both']['FA']['mean']}/{rec['rho_both']['D1']['mean']}",
                f"{rec['both_timing']['FA_earlier']}/{rec['both_timing']['same']}/{rec['both_timing']['FA_later']}",
                f"{rec['fa_only']['mean_rho']}/{rec['fa_only']['mean_d']}",
            ])
        lines.append(_md_table(tab))
        lines.append("")
        for tag, rec in comps.items():
            lines.append(f"#### {tag} 清单")
            lines.append("")
            nmap = {"both": "n_both", "fa_only": "n_fa_only", "d1_only": "n_d1_only", "none": "n_none"}
            for name in ("both", "fa_only", "d1_only", "none"):
                cells = ", ".join(f"{x['attack']}/s{x['seed']}" for x in rec["list"][name]) or "—"
                lines.append(f"- {name} ({rec[nmap[name]]}): {cells}")
            lines.append("")
    lines += ["## B ladder CADETS b=5", ""]
    tab = [["步", "ΔE", "E after", "n_changed"]]
    for s in b["steps"]:
        tab.append([s["step"], f"{s['dE']:.6f}", f"{s['E_after']:.6f}", s["n_changed"]])
    lines.append(_md_table(tab))
    lines.append("")
    for s in b["steps"]:
        lines.append(f"### {s['step']}")
        lines.append("")
        if not s["changed"]:
            lines.append("无变化 cell。")
            lines.append("")
            continue
        t = [["attack", "seed", "ρ before", "ρ after", "hit before", "hit after"]]
        for x in s["changed"]:
            t.append([x["attack"], x["seed"], x["rho_before"], x["rho_after"], x["hit_before"], x["hit_after"]])
        lines.append(_md_table(t))
        lines.append("")
    lines += ["## C evidence chain（37 个 FA 首告警）", "",
              f"- 链含 M_i：{c['n_chain_M']}/{c['n']}；CADETS b=5：{c['cadets_b5']['n_chain_M']}/{c['cadets_b5']['n']}",
              f"- 告警 process = 入口 process：{c['n_entry']}/{c['n']}",
              f"- 跨 process：{c['n_cross']}/{c['n']}",
              f"- 通道：{c['by_channel']}",
              ""]
    t = [["ds", "attack", "seed", "b", "ch", "entry?", "cross", "n_ev", "n_mal", "malΔ/W"]]
    for r in c["rows"]:
        t.append([
            r["dataset"], r["attack"], r["seed"], r["b"], r["channel"],
            r.get("is_entry"), r.get("cross_process"), r.get("n_events"), r.get("n_malicious"),
            "" if r.get("mal_inc_over_W") is None else f"{r['mal_inc_over_W']:.4f}",
        ])
    lines.append(_md_table(t))
    lines.append("")
    lines += ["## D placebo CADETS b=5", ""]
    t = [["seed", "day", "d_cell", "n_pre", "first", "mean_gap", "p(L=d)", "p(83)", "p(174)"]]
    for r in d["attack_days"]:
        pd_ = r["p_placebo"]
        keys = list(pd_)
        p_d = pd_[keys[0]]["p"] if r["d_cell"] is not None else None
        t.append([
            r["seed"], r["day"], "" if r["d_cell"] is None else f"{r['d_cell']:.3f}",
            r["n_alert_before_t0"], r["first_alert"],
            "" if r["mean_interval_s"] is None else f"{r['mean_interval_s']:.3f}",
            p_d, pd_.get("83.0", {}).get("p"), pd_.get("174.0", {}).get("p"),
        ])
    lines.append(_md_table(t))
    lines.append("")
    lines.append("### 其他日（有 nginx 告警才给 p）")
    lines.append("")
    t = [["seed", "day", "n_alert", "first", "p(83)", "p(174)"]]
    for r in d["other_days"]:
        if not r.get("has_alert"):
            t.append([r["seed"], r["day"], 0, "none", "", ""])
            continue
        t.append([
            r["seed"], r["day"], r.get("n_alert"), r.get("first_alert"),
            (r.get("p_placebo") or {}).get("83.0", {}).get("p"),
            (r.get("p_placebo") or {}).get("174.0", {}).get("p"),
        ])
    lines.append(_md_table(t))
    lines.append("")
    lines += ["## E F 与 F′", ""]
    t = [["dataset", "b", "rule", "F", "F′"]]
    for ds, bb in e.items():
        for bgt, rec in bb.items():
            for rule, v in rec.items():
                t.append([ds, bgt, "FA" if rule == "D4" else rule, f"{v['F']:.4f}", f"{v['F_prime']:.4f}"])
    lines.append(_md_table(t))
    lines.append("")
    path = OUT / "DECOMP_v9_6.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _sels():
    out = {}
    for ds in DATASETS:
        s = json.loads((ART_ROOT / ds / "selection.json").read_text(encoding="utf-8"))
        out[ds] = (s["cap"], s["prior"])
    return out


def _parallel(fn, items, workers):
    if workers <= 1 or len(items) <= 1:
        return [fn(it) for it in items]
    out = [None] * len(items)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in as_completed(futs):
            out[futs[fut]] = fut.result()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all", choices=["cells", "replay", "report", "all"])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_cells()
    a = step_a(rows)
    b = step_b(rows)
    chk_ab = self_check_ab(rows, a, b)
    (OUT / "CHECK_AB.json").write_text(json.dumps({"A": a, "B": b, "check": chk_ab}, indent=2, default=_json), encoding="utf-8")
    print(f"[cells] A/B ok={chk_ab['ok']} flags={chk_ab['flags']} E={chk_ab['E_raw']}", flush=True)
    if not chk_ab["ok"]:
        print("A/B 自检失败，停止。", flush=True)
        return 2
    if args.phase == "cells":
        return 0

    sels = _sels()
    if args.phase in ("replay", "all"):
        items = [(ds, int(s), *sels[ds]) for ds in DATASETS for s in SEEDS]
        missing = [it for it in items if not (CACHE / f"{it[0]}_seed{it[1]}.json").is_file()]
        if missing:
            _parallel(replay_seed, missing, args.workers)
        else:
            print("[replay] cache hit", flush=True)

    blobs = load_caches()
    c = step_c(blobs, rows)
    chk_c = self_check_c(c)
    print(f"[C] ok={chk_c['ok']} {c['n_chain_M']}/{c['n']} cadets_b5={c['cadets_b5']}", flush=True)
    if not chk_c["ok"]:
        (OUT / "CHECK_C.json").write_text(json.dumps({"C": c, "check": chk_c}, indent=2, default=_json), encoding="utf-8")
        print("C 自检失败，停止。", flush=True)
        return 2
    d = step_d(blobs, rows)
    e = step_e(blobs)
    write_report(a, b, c, d, e, chk_ab, chk_c)
    payload = {"A": a, "B": b, "C": c, "D": d, "E": e, "check_ab": chk_ab, "check_c": chk_c}
    (OUT / "DECOMP_v9_6.json").write_text(json.dumps(payload, indent=2, default=_json), encoding="utf-8")
    print(f"wrote {OUT / 'DECOMP_v9_6.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
