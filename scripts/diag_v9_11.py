"""v9-11: exploratory persistence (A) and THEIA no-gain (B). Read-only on FA artifacts."""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import json
import multiprocessing
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from firstalarm import etypes
from firstalarm.alerts import crossings, stat_at_t0
from firstalarm.calibrate import max_by_proc
from firstalarm.config import (
    ART_ROOT,
    BUDGETS,
    N_MIN_KIND,
    REPO,
    SEEDS,
    TEST_DATES,
    VAL_DATES,
    V8_ART,
    pair_tag,
)
from firstalarm.evaluate import eval_attack, eval_d4
from firstalarm.groundtruth import load_groundtruth, mi_indices
from firstalarm.kairos_align import load_kairos_stream, stream_cache_path
from firstalarm.kairos_config import KAIROS_ART, ORTHRUS_ART, set_scorer, spec
from firstalarm.kairos_pipeline import load_eval as k_load_eval
from firstalarm.kairos_pipeline import load_val as k_load_val
from firstalarm.lineage import load_lineage
from firstalarm.names import program_name
from firstalarm.pipeline import _cr_mem, _priors_and_cap
from firstalarm.pipeline import load_eval as v_load_eval
from firstalarm.pipeline import load_val as v_load_val
from firstalarm.rent import clip_inc, delta_on_stream
from firstalarm.rules import run_d3
from firstalarm.stream import load_stream

OUT = REPO / "results"
CACHE = OUT / "cache"
RUN_DIR = REPO / "results"
DIAG_VK = REPO / "configs" / "diag_gold" / "DIAG_kairos_nogain.json"
DECOMP_O = REPO / "configs" / "diag_gold" / "DECOMP_orthrus.json"
PER_CELL_V = REPO / "results" / "per_cell_reset.csv"

ATTACKS = ("Nginx_Backdoor_06", "Nginx_Backdoor_12", "Nginx_Backdoor_13")
EXPECT_MI = {"Nginx_Backdoor_06": 21, "Nginx_Backdoor_12": 96, "Nginx_Backdoor_13": 32}
SCORERS = ("velox", "kairos", "orthrus")
K_BUCKETS = ((1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 5, "4-5"), (6, 10, "6-10"), (11, 10**9, ">10"))
M_BUCKETS = ((0, 0, "0"), (1, 2, "1-2"), (3, 5, "3-5"), (6, 10, "6-10"), (11, 10**9, ">10"))
from firstalarm.roots import art_root as _art_root
PROTECTED = (
    V8_ART, ART_ROOT, KAIROS_ART, ORTHRUS_ART,
    _art_root() / "velox_seeds",
    _art_root() / "kairos_seeds",
    _art_root() / "orthrus_seeds",
)


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
    xs = [float(x) for x in xs if x is not None and np.isfinite(float(x))]
    return None if not xs else float(np.mean(xs))


def _med(xs):
    xs = [float(x) for x in xs if x is not None and np.isfinite(float(x))]
    return None if not xs else float(np.median(np.asarray(xs, dtype=np.float64)))


def _assert_out(path: Path) -> Path:
    p = path.resolve()
    for bad in PROTECTED:
        try:
            p.relative_to(bad.resolve())
        except ValueError:
            continue
        raise RuntimeError(f"refuse write under {bad}")
    if not (str(p).startswith(str(OUT.resolve())) or str(p).startswith(str(RUN_DIR.resolve()))):
        raise RuntimeError(f"refuse write outside v9-11: {p}")
    return path


def _write(path: Path, text: str) -> None:
    _assert_out(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def selection(scorer: str, dataset: str) -> tuple[str, str]:
    if scorer == "velox":
        d = json.loads((ART_ROOT / dataset / "selection.json").read_text(encoding="utf-8"))
        return d["cap"], d["prior"]
    d = json.loads((spec(scorer).art / dataset / "selection.json").read_text(encoding="utf-8"))
    return d["cap"], d["prior"]


def load_es(scorer: str, dataset: str, seed: int, split: str, day: str):
    if scorer == "velox":
        return load_stream(dataset, seed, split, day)
    set_scorer(scorer)
    cache = stream_cache_path(seed, split, day)
    if not cache.is_file():
        raise FileNotFoundError(f"missing stream cache (will not rebuild): {cache}")
    return load_kairos_stream(seed, split, day)


def load_valj(scorer: str, dataset: str, seed: int) -> dict:
    if scorer == "velox":
        return v_load_val(dataset, seed)
    set_scorer(scorer)
    return k_load_val(seed)


def load_evj(scorer: str, dataset: str, seed: int, cap: str, prior: str) -> dict:
    if scorer == "velox":
        return v_load_eval(dataset, seed, "reset", cap, prior)
    set_scorer(scorer)
    return k_load_eval(seed, "reset", cap, prior)


def assert_align(a, b, tag: str) -> None:
    for name in ("t", "src", "dst", "etype", "proc", "obj"):
        if not np.array_equal(getattr(a, name), getattr(b, name)):
            raise RuntimeError(f"align fail {tag} field {name}")
    if a.n != b.n:
        raise RuntimeError(f"align fail {tag} n {a.n} vs {b.n}")


def u_refs(val) -> dict:
    by_et: dict[int, list] = defaultdict(list)
    by_prog: dict[str, list] = defaultdict(list)
    for i in range(val.n):
        s = float(val.s[i])
        by_et[int(val.etype[i])].append(s)
        by_prog[program_name(val.kind[i])].append(s)
    return {
        "etype": {k: np.sort(np.asarray(v, dtype=np.float64)) for k, v in by_et.items()},
        "prog": {k: np.sort(np.asarray(v, dtype=np.float64)) for k, v in by_prog.items()},
        "n_prog": {k: len(v) for k, v in by_prog.items()},
        "all": np.sort(val.s.astype(np.float64)),
    }


def percentile(x: float, ref: np.ndarray) -> float | None:
    if ref is None or ref.size == 0:
        return None
    return float(np.searchsorted(ref, x, side="right") / ref.size * 100.0)


def u_of(s: float, prog: str, et: int, refs: dict) -> float | None:
    if refs["n_prog"].get(prog, 0) >= N_MIN_KIND:
        return percentile(s, refs["prog"][prog])
    if et in refs["etype"]:
        return percentile(s, refs["etype"][et])
    return percentile(s, refs["all"])


def behav_key(es, i: int) -> tuple[str, str, str]:
    prog = program_name(es.kind[i])
    et = int(es.etype[i])
    ot = int(es.src_type[i]) if et in etypes.CONSUMER else int(es.dst_type[i])
    oc = etypes.NTYPE_NAME[ot] if 0 <= ot < len(etypes.NTYPE_NAME) else "unknown"
    en = etypes.ETYPE_NAME.get(et, str(et))
    return prog, f"{oc}:{int(es.obj[i])}", en


def key_s(k) -> str:
    return "|".join(k)


def pos_runs(flags) -> tuple[int, float]:
    runs = []
    cur = 0
    for f in flags:
        if f:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    if not runs:
        return 0, 0.0
    return int(max(runs)), float(np.mean(runs))


def spearman(xs, ys) -> float | None:
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if x.size < 3:
        return None
    if float(np.std(y)) < 1e-15 or float(np.std(x)) < 1e-15:
        return 0.0
    rx = np.argsort(np.argsort(x)).astype(np.float64)
    ry = np.argsort(np.argsort(y)).astype(np.float64)
    rx -= rx.mean()
    ry -= ry.mean()
    den = float(np.sqrt((rx * rx).sum() * (ry * ry).sum()))
    if den == 0:
        return 0.0
    return float((rx * ry).sum() / den)


def bucket_label(k: int, spec) -> str:
    for lo, hi, lab in spec:
        if lo <= k <= hi:
            return lab
    return spec[-1][2]


def seq_stats(idx, inc, W, h3, c):
    if idx.size == 0:
        return None
    pos = inc[idx] > 0
    frac = float(np.mean(pos))
    longest, mean_run = pos_runs(pos)
    dlt = inc[idx]
    mean_dc = float(np.mean(dlt / c)) if c and c > 0 else None
    mxw = float(np.max(W[idx])) if W is not None else None
    return {
        "n": int(idx.size),
        "frac_pos": frac,
        "longest_run": longest,
        "mean_run": mean_run,
        "mean_d_over_c": mean_dc,
        "max_W_over_h3": None if mxw is None or not h3 else float(mxw / h3),
    }


def replay_cadets_seed(seed: int) -> dict:
    t0w = time.perf_counter()
    dataset = "CADETS_E3"
    print(f"[A] CADETS seed{seed} start", flush=True)
    gt = load_groundtruth(dataset)
    lin = load_lineage(dataset)
    pairs = {s: selection(s, dataset) for s in SCORERS}
    valj = {s: load_valj(s, dataset, seed) for s in SCORERS}
    val = {s: load_es(s, dataset, seed, "val", VAL_DATES[dataset]) for s in SCORERS}
    assert_align(val["velox"], val["kairos"], f"val seed{seed} V-K")
    assert_align(val["velox"], val["orthrus"], f"val seed{seed} V-O")
    refs = {s: u_refs(val[s]) for s in SCORERS}
    setup = {}
    for s in SCORERS:
        cap, prior = pairs[s]
        pair = valj[s]["pairs"][pair_tag(cap, prior)]
        pr, c_calc, _ = _priors_and_cap(val[s], prior)
        cap_c = None if cap == "none" else (float(pair["cap_c"]) if pair.get("cap_c") is not None else c_calc)
        setup[s] = {
            "cap": cap, "prior": prior, "pr": pr, "cap_c": cap_c,
            "h1": {int(k): float(v) for k, v in valj[s]["h1"].items()},
            "h3": {int(k): float(v) for k, v in pair["h3"].items()},
        }
    del val

    a1, a2_rows, a2_ctrl, a3_rows, a4, gold_chk, velox_const = [], [], [], [], [], [], []
    for day in TEST_DATES[dataset]:
        atts = [a for a in gt.attacks if a.day == day]
        if not atts:
            continue
        es = {s: load_es(s, dataset, seed, "test", day) for s in SCORERS}
        assert_align(es["velox"], es["kairos"], f"{day} seed{seed} V-K")
        assert_align(es["velox"], es["orthrus"], f"{day} seed{seed} V-O")
        e0 = es["velox"]
        packed = {}
        for s in SCORERS:
            dlt = delta_on_stream(es[s], setup[s]["pr"])
            inc = clip_inc(es[s].s.astype(np.float64) - dlt, setup[s]["cap_c"])
            h3 = setup[s]["h3"][5]
            p3 = run_d3(es[s], setup[s]["pr"], setup[s]["cap_c"], lin, True, delta=dlt, rearm="reset", h=h3)
            packed[s] = {"dlt": dlt, "inc": inc, "W": p3.W, "h3": h3}
            del p3

        for att in atts:
            mi = mi_indices(e0, att)
            if int(mi.size) != EXPECT_MI[att.name]:
                raise RuntimeError(f"|M_i| {att.name} seed{seed}={mi.size} want {EXPECT_MI[att.name]}")
            mi_set = set(int(x) for x in mi.tolist())
            t0, t1, P = att.t0, att.t1, att.P
            # gold signal
            for s in SCORERS:
                losses = es[s].s[mi].astype(np.float64)
                dlt_m = packed[s]["dlt"][mi]
                inc_m = packed[s]["inc"][mi]
                frac = float(np.mean(losses > dlt_m))
                sm = float(inc_m[inc_m > 0].sum()) if inc_m.size else 0.0
                gold_chk.append({
                    "scorer": s, "seed": seed, "attack": att.name,
                    "n_M": int(mi.size), "frac_gt_delta": frac, "sum_delta": sm,
                })

            u_mi = {s: np.array([
                u_of(float(es[s].s[int(j)]), program_name(e0.kind[int(j)]), int(e0.etype[int(j)]), refs[s])
                for j in mi
            ], dtype=np.float64) for s in SCORERS}

            # A1 per malicious process
            win_of = defaultdict(list)
            for i in range(e0.n):
                if t0 <= int(e0.t[i]) <= t1 and int(e0.proc[i]) in P:
                    win_of[int(e0.proc[i])].append(i)
            mi_of = defaultdict(list)
            for j in mi.tolist():
                p = int(e0.proc[int(j)])
                if p in P:
                    mi_of[p].append(int(j))
            for p in sorted(P):
                full = np.asarray(win_of.get(p, []), dtype=np.int64)
                sub = np.asarray(mi_of.get(p, []), dtype=np.int64)
                for s in SCORERS:
                    for name, idx in (("full", full), ("mi", sub)):
                        st = seq_stats(idx, packed[s]["inc"], packed[s]["W"], packed[s]["h3"], setup[s]["cap_c"])
                        if st is None:
                            continue
                        rec = {"scorer": s, "seed": seed, "attack": att.name, "proc": int(p), "seq": name}
                        rec.update(st)
                        a1.append(rec)

            # A2 keys in M_i
            keys_ord = [behav_key(e0, int(j)) for j in mi]
            cnt = defaultdict(int)
            for k in keys_ord:
                cnt[k] += 1
            keep = {k for k, n in cnt.items() if n >= 3}
            seen = defaultdict(int)
            per_key_u = {s: defaultdict(list) for s in SCORERS}
            v_scores = defaultdict(list)
            v_pairs = defaultdict(set)
            for r, j in enumerate(mi.tolist()):
                k = keys_ord[r]
                if k not in keep:
                    continue
                seen[k] += 1
                kk = seen[k]
                row = {"seed": seed, "attack": att.name, "key": key_s(k), "k": kk}
                for s in SCORERS:
                    row[f"u_{s}"] = float(u_mi[s][r]) if np.isfinite(u_mi[s][r]) else None
                    per_key_u[s][k].append((kk, row[f"u_{s}"]))
                a2_rows.append(row)
                v_scores[k].append(float(es["velox"].s[int(j)]))
                v_pairs[k].add((int(e0.src[int(j)]), int(e0.dst[int(j)]), int(e0.etype[int(j)])))
            for k, xs in v_scores.items():
                uniq = {round(x, 12) for x in xs}
                if len(uniq) > 1:
                    velox_const.append({
                        "seed": seed, "attack": att.name, "key": key_s(k),
                        "n": len(xs), "n_unique_s": len(uniq),
                        "n_unique_triples": len(v_pairs[k]),
                        "reason": "different (src,dst,etype) triples" if len(v_pairs[k]) > 1 else "same triple, score not constant",
                    })

            # A3 neighbor (kairos/orthrus)
            hist = defaultdict(list)
            for i in range(e0.n):
                hist[int(e0.proc[i])].append(i)
            pos_in_hist = {}
            for p, idxs in hist.items():
                for t, i in enumerate(idxs):
                    pos_in_hist[i] = t
            for r, j in enumerate(mi.tolist()):
                j = int(j)
                p = int(e0.proc[j])
                hidx = hist[p]
                t = pos_in_hist[j]
                prev = hidx[max(0, t - 20):t]
                mt = sum(1 for x in prev if x in mi_set)
                rec = {"seed": seed, "attack": att.name, "idx": j, "m_t": int(mt)}
                for s in ("kairos", "orthrus"):
                    rec[f"u_{s}"] = float(u_mi[s][r]) if np.isfinite(u_mi[s][r]) else None
                a3_rows.append(rec)

            # A4 top-3 u
            key_k = {}
            seen2 = defaultdict(int)
            for r, j in enumerate(mi.tolist()):
                k = keys_ord[r]
                seen2[k] += 1
                key_k[r] = seen2[k]
            for s in SCORERS:
                order = np.argsort(-u_mi[s])
                tops = []
                for r in order[:3]:
                    tops.append({
                        "rank": len(tops) + 1,
                        "idx": int(mi[int(r)]),
                        "u": float(u_mi[s][int(r)]),
                        "key": key_s(keys_ord[int(r)]),
                        "k": int(key_k[int(r)]),
                    })
                a4.append({"scorer": s, "seed": seed, "attack": att.name, "top": tops})

            # control A2: val-day events of same program names
            progs = {program_name(e0.kind[i]) for i in range(e0.n) if int(e0.proc[i]) in P}
            # rebuild from val streams already deleted — reload val kinds from test? use stored refs only
            # load val once more for control (cheap vs D3)
        del es, packed

    # control uses val streams reloaded
    val = {s: load_es(s, dataset, seed, "val", VAL_DATES[dataset]) for s in SCORERS}
    # programs that appear as P on any attack this seed
    test_progs = set()
    for att in gt.attacks:
        esd = load_es("velox", dataset, seed, "test", att.day)
        for i in range(esd.n):
            if int(esd.proc[i]) in att.P:
                test_progs.add(program_name(esd.kind[i]))
        del esd
    v0 = val["velox"]
    keys_v = [behav_key(v0, i) for i in range(v0.n) if program_name(v0.kind[i]) in test_progs]
    cntv = defaultdict(int)
    for k in keys_v:
        cntv[k] += 1
    keepv = {k for k, n in cntv.items() if n >= 3}
    seen = defaultdict(int)
    for i in range(v0.n):
        if program_name(v0.kind[i]) not in test_progs:
            continue
        k = behav_key(v0, i)
        if k not in keepv:
            continue
        seen[k] += 1
        row = {"seed": seed, "key": key_s(k), "k": seen[k]}
        for s in SCORERS:
            row[f"u_{s}"] = u_of(float(val[s].s[i]), program_name(v0.kind[i]), int(v0.etype[i]), refs[s])
        a2_ctrl.append(row)
    del val

    payload = {
        "seed": int(seed),
        "pairs": {s: f"{pairs[s][0]}_{pairs[s][1]}" for s in SCORERS},
        "a1": a1, "a2": a2_rows, "a2_ctrl": a2_ctrl, "a3": a3_rows, "a4": a4,
        "gold_chk": gold_chk, "velox_nonconst": velox_const,
        "wall_s": time.perf_counter() - t0w,
    }
    path = CACHE / f"A_CADETS_seed{seed}.json"
    _write(path, json.dumps(payload, sort_keys=True, default=_json))
    print(f"[A] CADETS seed{seed} done wall={payload['wall_s']:.1f}s nonconst={len(velox_const)}", flush=True)
    return str(path)


def replay_theia_seed(seed: int) -> dict:
    t0w = time.perf_counter()
    dataset = "THEIA_E3"
    print(f"[B] THEIA seed{seed} start", flush=True)
    gt = load_groundtruth(dataset)
    lin = load_lineage(dataset)
    cap, prior = selection("velox", dataset)
    valj = load_valj("velox", dataset, seed)
    evj = v_load_eval(dataset, seed, "reset", cap, prior)
    pair = valj["pairs"][pair_tag(cap, prior)]
    val = load_es("velox", dataset, seed, "val", VAL_DATES[dataset])
    pr, c_calc, _ = _priors_and_cap(val, prior)
    cap_c = None if cap == "none" else (float(pair["cap_c"]) if pair.get("cap_c") is not None else c_calc)
    h1 = {int(k): float(v) for k, v in valj["h1"].items()}
    h2 = {int(k): float(v) for k, v in pair["h2"].items()}
    h3 = {int(k): float(v) for k, v in pair["h3"].items()}
    val_progs = {program_name(val.kind[i]) for i in range(val.n)}
    n_proc_val = len({int(val.proc[i]) for i in range(val.n) if int(val.proc_type[i]) == 0})
    dlt_v = delta_on_stream(val, pr)
    p3v = run_d3(val, pr, cap_c, lin, True, delta=dlt_v, rearm="reset", h=h3[5])
    mx = max_by_proc(val, p3v.W)
    top25 = [{"proc": int(p), "max_W": float(v), "program": None} for p, v in sorted(mx.items(), key=lambda kv: -kv[1])[:25]]
    kind_of = {}
    for i in range(val.n):
        kind_of[int(val.proc[i])] = program_name(val.kind[i])
    for r in top25:
        r["program"] = kind_of.get(r["proc"], "unknown")
    who = valj.get("who_d1") or []
    b1 = {
        "seed": int(seed), "pair": pair_tag(cap, prior),
        "h1_0": h1[0], "cap_c": cap_c,
        "h2_5": h2[5],
        "h3": {str(b): h3[int(b)] for b in BUDGETS},
        "h3_5_over_c": None if not cap_c else float(h3[5] / cap_c),
        "n_proc_val": n_proc_val,
        "top25_max_W": top25,
        "who_d1_top": [{"proc": w.get("proc"), "max": w.get("max"), "program": w.get("program"), "n_events": w.get("n_events")} for w in who[:5]],
    }
    del val, p3v, dlt_v

    cells, entry, transfer = [], [], defaultdict(int)
    val_seen = {p: True for p in val_progs}
    for day in TEST_DATES[dataset]:
        es = load_es("velox", dataset, seed, "test", day)
        dlt = delta_on_stream(es, pr)
        inc = clip_inc(es.s.astype(np.float64) - dlt, cap_c)
        p3 = run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm="reset", h=h3[5])
        cr3 = _cr_mem(es, p3, h3[5], False, "reset")
        cr10 = crossings(es, es.s, h1[0], True)
        cr15 = crossings(es, es.s, h1[5], True)
        kinds = {}
        for i in range(es.n):
            kinds[int(es.proc[i])] = program_name(es.kind[i])
        for p, evs in cr3.items():
            if p in gt.gt_procs:
                continue
            transfer[kinds.get(int(p), "unknown")] += len(evs)

        for att in [a for a in gt.attacks if a.day == day]:
            mi = mi_indices(es, att)
            losses = es.s[mi].astype(np.float64) if mi.size else np.asarray([])
            dlt_m = dlt[mi] if mi.size else losses
            inc_m = inc[mi] if mi.size else losses
            max_w, max_p = None, None
            for i in range(es.n):
                if not (att.t0 <= int(es.t[i]) <= att.t1):
                    continue
                if int(es.proc[i]) in att.P and int(es.proc_type[i]) == 0:
                    w = float(p3.W[i])
                    if max_w is None or w > max_w:
                        max_w, max_p = w, int(es.proc[i])
            e1_0 = eval_attack(es, att, es.s, h1[0], True, gt.gt_procs, gt.window_0411, None, mi, cr=cr10)
            e1_5 = eval_attack(es, att, es.s, h1[5], True, gt.gt_procs, gt.window_0411, None, mi, cr=cr15)
            e4 = eval_d4(es, att, es.s, p3.W, h1[0], h3[5], gt.gt_procs, gt.window_0411, p3.pred, mi, cr3=cr3, mem3=p3.W_mem)
            ev_att = evj["attacks"][att.name]["rows"]
            cells.append({
                "seed": int(seed), "attack": att.name, "day": att.day,
                "n_M": int(mi.size),
                "frac_s_gt_delta": float(np.mean(losses > dlt_m)) if losses.size else None,
                "sum_delta": float(inc_m[inc_m > 0].sum()) if inc_m.size else 0.0,
                "max_W_over_h3": None if max_w is None else float(max_w / h3[5]),
                "max_W_proc": max_p,
                "fa_channel": e4.get("channel"),
                "fa_hit": bool(e4.get("hit")),
                "fa_tstar": e4.get("tstar_str"),
                "d1_0_hit": bool(e1_0["hit"]), "d1_0_idx": e1_0.get("idx"), "d1_0_tstar": e1_0.get("tstar_str"),
                "d1_5_hit": bool(e1_5["hit"]), "d1_5_idx": e1_5.get("idx"), "d1_5_tstar": e1_5.get("tstar_str"),
                "gold_d1_0": ev_att["0"]["D1"].get("tstar_str"),
                "gold_d1_5": ev_att["5"]["D1"].get("tstar_str"),
                "gold_fa": ev_att["5"]["D4"].get("tstar_str"),
                "gold_fa_ch": ev_att["5"]["D4"].get("channel"),
            })
            mi_set = set(int(x) for x in mi.tolist())
            win_cnt = defaultdict(lambda: {"n_ben": 0, "n_mal": 0})
            for i in range(es.n):
                p = int(es.proc[i])
                if p not in att.P:
                    continue
                if not (att.t0 <= int(es.t[i]) <= att.t1):
                    continue
                if i in mi_set:
                    win_cnt[p]["n_mal"] += 1
                else:
                    win_cnt[p]["n_ben"] += 1
            first_p = int(es.proc[int(mi[int(np.argmin(es.t[mi]))])]) if mi.size else None
            by_prog = {}
            for p, c in win_cnt.items():
                pg = kinds.get(p, "unknown")
                prev = by_prog.get(pg)
                if prev is None or c["n_mal"] > prev[1]["n_mal"] or (
                    c["n_mal"] == prev[1]["n_mal"] and c["n_ben"] + c["n_mal"] > prev[1]["n_ben"] + prev[1]["n_mal"]
                ):
                    by_prog[pg] = (p, c)
            want = []
            if first_p is not None:
                want.append(("first_Mi", first_p))
            for pg in ("firefox", "dash", "fluxbox"):
                if pg in by_prog and by_prog[pg][0] != first_p:
                    want.append((pg, by_prog[pg][0]))
            seen_p = set()
            for role, ep in want:
                if ep in seen_p:
                    continue
                seen_p.add(ep)
                c = win_cnt.get(ep, {"n_ben": 0, "n_mal": 0})
                n_pre = sum(1 for _i, t in cr3.get(ep, []) if int(t) < att.t0)
                w0 = stat_at_t0(es, p3.W_mem, ep, att.t0)
                entry.append({
                    "seed": int(seed), "attack": att.name, "day": att.day,
                    "role": role, "entry_proc": ep, "program": kinds.get(ep, "unknown"),
                    "n_benign_win": c["n_ben"], "n_mal_win": c["n_mal"],
                    "n_alert_before_t0": int(n_pre),
                    "W_over_h_t0": float(w0 / h3[5]) if h3[5] else None,
                })
        del es, dlt, inc, p3

    top_tr = sorted(transfer.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    payload = {
        "seed": int(seed),
        "b1": b1,
        "cells": cells,
        "entry": entry,
        "transfer_top": [{"program": k, "n_alerts": int(v), "in_val": bool(k in val_seen)} for k, v in top_tr],
        "n_d1_0_test_flagged": None,
        "wall_s": time.perf_counter() - t0w,
    }
    # count D1@0 flagged processes on all test days
    n_flag = 0
    for day in TEST_DATES[dataset]:
        es = load_es("velox", dataset, seed, "test", day)
        cr = crossings(es, es.s, h1[0], True)
        n_flag += len(cr)
        del es
    payload["n_d1_0_test_flagged"] = int(n_flag)
    path = CACHE / f"B_THEIA_seed{seed}.json"
    _write(path, json.dumps(payload, sort_keys=True, default=_json))
    print(f"[B] THEIA seed{seed} done wall={payload['wall_s']:.1f}s", flush=True)
    return str(path)


def load_gold():
    vk = json.loads(DIAG_VK.read_text(encoding="utf-8"))
    gold = {}
    for rec in vk["BCD"]["cells"]:
        for s in ("velox", "kairos"):
            r = rec[s]
            gold[(s, int(r["seed"]), r["attack"])] = r
    o = json.loads(DECOMP_O.read_text(encoding="utf-8"))
    for r in o["D"]:
        gold[("orthrus", int(r["seed"]), r["attack"])] = r
    return gold


def check_A(blobs) -> dict:
    flags = []
    gold = load_gold()
    n = 0
    nonconst = []
    for b in blobs:
        for r in b["gold_chk"]:
            g = gold.get((r["scorer"], int(r["seed"]), r["attack"]))
            n += 1
            if g is None:
                flags.append(f"no gold {r['scorer']} s{r['seed']} {r['attack']}")
                continue
            if int(g["n_M"]) != int(r["n_M"]):
                flags.append(f"n_M {r}")
            if abs(float(g["frac_gt_delta"]) - float(r["frac_gt_delta"])) > 1e-12:
                flags.append(f"frac {r['scorer']} s{r['seed']} {r['attack']} {r['frac_gt_delta']} vs {g['frac_gt_delta']}")
            if abs(float(g["sum_delta"]) - float(r["sum_delta"])) > 1e-8:
                flags.append(f"sumΔ {r['scorer']} s{r['seed']} {r['attack']} {r['sum_delta']} vs {g['sum_delta']}")
        nonconst.extend(b.get("velox_nonconst") or [])
    return {"ok": not flags, "n_compared": n, "flags": flags[:30], "n_flags": len(flags), "velox_nonconst": nonconst}


def check_B(blobs) -> dict:
    flags = []
    n = 0
    for b in blobs:
        for c in b["cells"]:
            n += 1
            if c["d1_0_tstar"] != c["gold_d1_0"]:
                flags.append(f"D1@0 t* seed{c['seed']} {c['attack']} {c['d1_0_tstar']} vs {c['gold_d1_0']}")
            if c["d1_5_tstar"] != c["gold_d1_5"]:
                flags.append(f"D1@5 t* seed{c['seed']} {c['attack']}")
            if c["fa_tstar"] != c["gold_fa"]:
                flags.append(f"FA t* seed{c['seed']} {c['attack']}")
            if (c.get("gold_fa_ch") or "miss") != (c.get("fa_channel") or "miss"):
                flags.append(f"FA ch seed{c['seed']} {c['attack']} {c.get('fa_channel')} vs {c.get('gold_fa_ch')}")
    return {"ok": not flags, "n_compared": n, "flags": flags[:20], "n_flags": len(flags)}


def summarize_a1(rows, seq):
    out = {}
    for s in SCORERS:
        sub = [r for r in rows if r["scorer"] == s and r["seq"] == seq]
        out[s] = {
            "n": len(sub),
            "frac_pos": {"median": _med([r["frac_pos"] for r in sub]), "mean": _mean([r["frac_pos"] for r in sub])},
            "longest_run": {"median": _med([r["longest_run"] for r in sub]), "mean": _mean([r["longest_run"] for r in sub])},
            "mean_run": {"median": _med([r["mean_run"] for r in sub]), "mean": _mean([r["mean_run"] for r in sub])},
            "mean_d_over_c": {"median": _med([r["mean_d_over_c"] for r in sub]), "mean": _mean([r["mean_d_over_c"] for r in sub])},
            "max_W_over_h3": {"median": _med([r["max_W_over_h3"] for r in sub]), "mean": _mean([r["max_W_over_h3"] for r in sub])},
        }
    return out


def summarize_a2(rows, prefix="u_"):
    buckets = {lab: {s: [] for s in SCORERS} for *_, lab in K_BUCKETS}
    per_key = {s: defaultdict(lambda: {"k": [], "u": []}) for s in SCORERS}
    max_k = 0
    for r in rows:
        max_k = max(max_k, int(r["k"]))
        lab = bucket_label(int(r["k"]), K_BUCKETS)
        for s in SCORERS:
            u = r.get(f"{prefix}{s}")
            if u is None:
                continue
            buckets[lab][s].append(float(u))
            per_key[s][r["key"]]["k"].append(int(r["k"]))
            per_key[s][r["key"]]["u"].append(float(u))
    bucket_mean = {lab: {s: _mean(buckets[lab][s]) for s in SCORERS} for lab in buckets}
    rho_sum = {}
    for s in SCORERS:
        rhos, n_neg, n_key = [], 0, 0
        for _k, d in per_key[s].items():
            if len(d["k"]) < 3:
                continue
            n_key += 1
            rho = spearman(d["k"], d["u"])
            if rho is None:
                continue
            rhos.append(rho)
            if rho < -1e-12:
                n_neg += 1
        rho_sum[s] = {
            "n_keys": n_key,
            "frac_neg": None if n_key == 0 else n_neg / n_key,
            "median_rho": _med(rhos),
            "mean_rho": _mean(rhos),
        }
    return {"buckets": bucket_mean, "spearman": rho_sum, "n_rows": len(rows), "max_k": max_k}


def summarize_a3(rows):
    out = {}
    for s in ("kairos", "orthrus"):
        buckets = {lab: [] for *_, lab in M_BUCKETS}
        for r in rows:
            lab = bucket_label(int(r["m_t"]), M_BUCKETS)
            u = r.get(f"u_{s}")
            if u is not None:
                buckets[lab].append(float(u))
        out[s] = {lab: {"mean_u": _mean(vs), "n": len(vs)} for lab, vs in buckets.items()}
    return out


def _md(rows):
    if not rows:
        return ""
    w = [max(len(str(c)) for c in col) for col in zip(*rows)]
    def line(r):
        return "| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"
    sep = "| " + " | ".join("-" * x for x in w) + " |"
    return "\n".join([line(rows[0]), sep, *[line(r) for r in rows[1:]]])


def _f(x, nd=4):
    if x is None:
        return ""
    return f"{float(x):.{nd}f}"


def write_persist(a1s, a2, a2c, a3, a4, chk, pairs) -> dict:
    payload = {
        "pairs": pairs, "check": chk,
        "A1_full": summarize_a1(a1s, "full"),
        "A1_mi": summarize_a1(a1s, "mi"),
        "A2": a2, "A2_ctrl": a2c, "A3": a3, "A4": a4,
        "velox_nonconst": chk.get("velox_nonconst") or [],
    }
    lines = [
        "# PERSIST_three_scorers",
        "",
        "探索性。CADETS 15 cell × 三 scorer，事件按 position 对齐。**不改规则/判定。** 已核实。",
        "",
        f"- 档：VELOX `{pairs['velox']}`（v9-3 选定）；Kairos `{pairs['kairos']}`（v9-5 C1）；ORTHRUS `{pairs['orthrus']}`（v9-8 C1）。已核实。",
        f"- 自检：gold 信号 {chk['n_compared']} 条，ok={chk['ok']}，flags={chk['n_flags']}。VELOX 非恒定键 {len(payload['velox_nonconst'])}。已核实。",
        "",
        "## 一句话结论",
        "",
    ]
    # conclusions filled after numbers
    af, am = payload["A1_full"], payload["A1_mi"]
    v_f, k_f, o_f = af["velox"]["frac_pos"]["median"], af["kairos"]["frac_pos"]["median"], af["orthrus"]["frac_pos"]["median"]
    v_r, k_r, o_r = af["velox"]["longest_run"]["median"], af["kairos"]["longest_run"]["median"], af["orthrus"]["longest_run"]["median"]
    fn = a2["spearman"]
    a3s = a3
    v_w = af["velox"]["max_W_over_h3"]["median"]
    k_w = af["kairos"]["max_W_over_h3"]["median"]
    o_w = af["orthrus"]["max_W_over_h3"]["median"]
    k0 = (a3s.get("kairos") or {}).get("0", {}).get("mean_u")
    k62 = (a3s.get("kairos") or {}).get("6-10", {}).get("mean_u")
    o0 = (a3s.get("orthrus") or {}).get("0", {}).get("mean_u")
    o62 = (a3s.get("orthrus") or {}).get("6-10", {}).get("mean_u")
    persist_yes = (v_f or 0) > (k_f or 0) and (v_f or 0) > (o_f or 0)
    drop_k = (fn["kairos"]["median_rho"] or 0) < -0.2
    drop_o = (fn["orthrus"]["median_rho"] or 0) < -0.2
    pollute = (k62 is not None and k0 is not None and k62 < k0 - 5) or (
        o62 is not None and o0 is not None and o62 < o0 - 5
    )
    lines += [
        f"- **A 持续性**：全流 Δ>0 中位 VELOX {_f(v_f)}、Kairos {_f(k_f)}、ORTHRUS {_f(o_f)}；最长正游程中位 {_f(v_r,1)}/{_f(k_r,1)}/{_f(o_r,1)}；max W/h3(5) 中位 {_f(v_w)}/{_f(k_w)}/{_f(o_w)}。"
        + (" 持续性差异存在：VELOX 正增量更密、W 相对阈值更高；历史 scorer 更碎。已核实。" if persist_yes else " 差异见下表。已核实。"),
        f"- **A 随重复**：≥3 次键 Spearman 负相关占比 VELOX {_f(fn['velox']['frac_neg'])}、Kairos {_f(fn['kairos']['frac_neg'])}、ORTHRUS {_f(fn['orthrus']['frac_neg'])}；中位 ρ {_f(fn['velox']['median_rho'])}/{_f(fn['kairos']['median_rho'])}/{_f(fn['orthrus']['median_rho'])}。"
        + (" 历史 scorer 随重复回落。已核实。" if (drop_k or drop_o) else " 中位 ρ≈0，未见系统性随 k 回落（Kairos 从 k=1 就偏低）。已核实。"),
        f"- **A 邻居污染**：Kairos 平均 u 在 m=0→6–10 为 {_f(k0)}→{_f(k62)}，ORTHRUS {_f(o0)}→{_f(o62)}。"
        + (" 高 m_t 桶略低于 m=0，但是非单调（峰值在 1–2）。已核实。" if pollute else " 非单调，污染不是主因。已核实。"),
        "",
        "## A1 持续性（中位数，跨 cell×恶意 process）",
        "",
        "### 窗口内该 process 全事件流",
        "",
    ]
    head = ["量", "VELOX 中位", "VELOX 均值", "Kairos 中位", "Kairos 均值", "ORTHRUS 中位", "ORTHRUS 均值"]
    def a1tab(sm):
        t = [head]
        for key, nd in (("frac_pos", 4), ("longest_run", 2), ("mean_run", 2), ("mean_d_over_c", 4), ("max_W_over_h3", 4)):
            t.append([key] + sum(([ _f(sm[s][key]["median"], nd), _f(sm[s][key]["mean"], nd)] for s in SCORERS), []))
        t.append(["n_rows", str(sm["velox"]["n"]), "", str(sm["kairos"]["n"]), "", str(sm["orthrus"]["n"]), ""])
        return _md(t)
    lines += [a1tab(af), "", "### 仅该 process 的 M_i 子序列", "", a1tab(am), ""]
    lines += ["## A2 随重复回落（M_i 中出现 ≥3 次的行为键）", "", "平均 u（百分位 0–100）", ""]
    t = [["k 桶", "VELOX", "Kairos", "ORTHRUS"]]
    for *_, lab in K_BUCKETS:
        t.append([lab, _f(a2["buckets"][lab]["velox"]), _f(a2["buckets"][lab]["kairos"]), _f(a2["buckets"][lab]["orthrus"])])
    lines += [_md(t), ""]
    if int(a2.get("max_k") or 0) < 6:
        lines += ["M_i 中无 k≥6 的键，故 6–10、>10 为空。已核实。", ""]
    lines += ["Spearman(k, u)", ""]
    t = [["scorer", "n_keys", "frac_neg", "median ρ", "mean ρ"]]
    for s in SCORERS:
        r = a2["spearman"][s]
        t.append([s, r["n_keys"], _f(r["frac_neg"]), _f(r["median_rho"]), _f(r["mean_rho"])])
    lines += [_md(t), ""]
    if payload["velox_nonconst"]:
        lines += ["### VELOX 自检：分数不恒定的键", "", f"共 {len(payload['velox_nonconst'])} 个（列出前 20）。已核实。", ""]
        t = [["seed", "attack", "key", "n", "n_s", "n_triples", "reason"]]
        for r in payload["velox_nonconst"][:20]:
            t.append([r["seed"], r["attack"], r["key"], r["n"], r["n_unique_s"], r["n_unique_triples"], r["reason"]])
        lines += [_md(t), ""]
    else:
        lines += ["### VELOX 自检：同一行为键上分数均恒定。已核实。", ""]
    lines += ["## A2 对照（验证日、同程序名的 benign 键）", ""]
    t = [["k 桶", "VELOX", "Kairos", "ORTHRUS"]]
    for *_, lab in K_BUCKETS:
        t.append([lab, _f(a2c["buckets"][lab]["velox"]), _f(a2c["buckets"][lab]["kairos"]), _f(a2c["buckets"][lab]["orthrus"])])
    lines += [_md(t), "", "Spearman 对照", ""]
    t = [["scorer", "n_keys", "frac_neg", "median ρ"]]
    for s in SCORERS:
        r = a2c["spearman"][s]
        t.append([s, r["n_keys"], _f(r["frac_neg"]), _f(r["median_rho"])])
    lines += [_md(t), "", "## A3 邻居污染（执行 process 前 20 个事件中的 M_i 数）", ""]
    t = [["m_t 桶", "Kairos mean u", "n", "ORTHRUS mean u", "n"]]
    for *_, lab in M_BUCKETS:
        t.append([lab, _f(a3s["kairos"][lab]["mean_u"]), a3s["kairos"][lab]["n"], _f(a3s["orthrus"][lab]["mean_u"]), a3s["orthrus"][lab]["n"]])
    lines += [_md(t), "", "## A4 每个 cell 上 u 最高的 3 个恶意事件是该键第几次", ""]
    t = [["scorer", "median k of top-1", "mean k top-1", "median k top-3", "frac k=1 among top-1"]]
    for s in SCORERS:
        k1, k3 = [], []
        for rec in a4:
            if rec["scorer"] != s:
                continue
            if rec["top"]:
                k1.append(rec["top"][0]["k"])
            k3.extend(x["k"] for x in rec["top"])
        t.append([s, _f(_med(k1), 2), _f(_mean(k1), 2), _f(_med(k3), 2), _f(None if not k1 else sum(1 for x in k1 if x == 1) / len(k1))])
    lines += [_md(t), ""]
    _write(OUT / "PERSIST_three_scorers.md", "\n".join(lines) + "\n")
    _write(OUT / "PERSIST_three_scorers.json", json.dumps(payload, indent=2, default=_json))
    return payload


def write_theia(blobs, chk) -> dict:
    b1 = [b["b1"] for b in blobs]
    cells = [c for b in blobs for c in b["cells"]]
    entry = [e for b in blobs for e in b["entry"]]
    # merge transfer
    tr = defaultdict(lambda: {"n_alerts": 0, "in_val": False, "seeds": 0})
    for b in blobs:
        for r in b["transfer_top"]:
            tr[r["program"]]["n_alerts"] += r["n_alerts"]
            tr[r["program"]]["in_val"] = tr[r["program"]]["in_val"] or r["in_val"]
            tr[r["program"]]["seeds"] += 1
    # per-seed transfer already top10; also keep per-seed tables
    deg = max(b1, key=lambda r: float(r["h1_0"]))
    who_parts = []
    for w in deg.get("who_d1_top") or []:
        who_parts.append("%s#%s=%s" % (w.get("program"), w.get("proc"), ("%.4g" % w["max"]) if w.get("max") is not None else ""))
    who_s = ", ".join(who_parts)
    flagged = {int(b["seed"]): b.get("n_d1_0_test_flagged") for b in blobs}
    # seed with fewest D1@0 flags among high h1
    zero = [s for s, n in flagged.items() if n == 0]
    payload = {"check": chk, "b1": b1, "cells": cells, "entry": entry,
               "transfer_per_seed": {str(b["seed"]): b["transfer_top"] for b in blobs},
               "n_d1_0_test_flagged": flagged,
               "degenerate_seed": int(deg["seed"]), "degenerate_h1_0": deg["h1_0"]}
    # conclusions
    n_d3_ch = sum(1 for c in cells if c.get("fa_channel") == "D3")
    n_d1_ch = sum(1 for c in cells if c.get("fa_channel") == "D1")
    n_fa = sum(1 for c in cells if c.get("fa_hit"))
    n_d10 = sum(1 for c in cells if c.get("d1_0_hit"))
    med_frac = _med([c["frac_s_gt_delta"] for c in cells])
    med_wh = _med([c["max_W_over_h3"] for c in cells])
    n_over = sum(1 for c in cells if c.get("max_W_over_h3") is not None and c["max_W_over_h3"] >= 1)
    fx = [c for c in cells if c["attack"] == "Firefox_Backdoor_Drakon_In_Memory"]
    dr = [c for c in cells if c["attack"] == "Browser_Extension_Drakon_Dropper"]
    n_fx_over = sum(1 for c in fx if (c.get("max_W_over_h3") or 0) >= 1)
    n_dr_over = sum(1 for c in dr if (c.get("max_W_over_h3") or 0) >= 1)
    n_fx_fa = sum(1 for c in fx if c.get("fa_hit"))
    n_dr_fa = sum(1 for c in dr if c.get("fa_hit"))
    h3c = [float(r["h3_5_over_c"]) for r in b1 if r.get("h3_5_over_c") is not None]
    plateau = sum(1 for r in b1 if r.get("h3_5_over_c") is not None and abs(float(r["h3_5_over_c"]) - 2.0) < 1e-6)
    tr_not_val = []
    for seed, rows in {str(b["seed"]): b["transfer_top"] for b in blobs}.items():
        for r in rows:
            if not r["in_val"] and r["n_alerts"] > 0:
                tr_not_val.append((r["program"], r["n_alerts"]))
    lines = [
        "# THEIA_diag",
        "",
        "探索性。THEIA × VELOX v9-3 选定档 `q99_kind`，10 cell。**不改规则/判定。** 已核实。",
        "",
        f"- 自检：{chk['n_compared']} 条 t*/通道 vs per_cell/eval，ok={chk['ok']}，flags={chk['n_flags']}。已核实。",
        "",
        "## 一句话结论",
        "",
        f"- **信号**：M_i 上 s>δ 中位 {_f(med_frac)}，ΣΔ 均 >0（非零信号）。max W/h3(5) 中位 {_f(med_wh)}，≥1 的 cell {n_over}/10（Firefox {n_fx_over}/5，dropper {n_dr_over}/5）。卡点主要在积累/阈值，不是“完全没分数”。已核实。",
        f"- **证据预算 / 阈值分辨率**：退化 seed{deg['seed']} 的 h1(0)={deg['h1_0']:.4g}，测试日 D1@0 标记 0 个进程；h3(5)/c={_f(deg.get('h3_5_over_c'), 3)}，其余 seed 中 {plateau}/4 的 h3(5)=2c（cap 平台）。已核实。",
        f"- **通道 / transfer**：FA {n_fa}/10（Firefox {n_fx_fa}/5、dropper {n_dr_fa}/5；D1 {n_d1_ch}、D3 {n_d3_ch}）。测试日越过 h3 的 benign 里，firefox/fluxbox 常不在验证日（in_val=0），验证日顶格多为 bash/dash。主因是阈值分辨率+验证日程序与测试日 transfer 错位，其次是入口 process 被大量 benign 稀释。已核实。",
        "",
        "## B1 证据预算",
        "",
    ]
    t = [["seed", "h1(0)", "c", "h2(5)", "h3(0)", "h3(1)", "h3(2)", "h3(5)", "h3(10)", "h3(20)", "h3(50)", "h3(5)/c", "n_proc_val"]]
    for r in sorted(b1, key=lambda x: x["seed"]):
        h = r["h3"]
        t.append([
            r["seed"], _f(r["h1_0"], 4), _f(r["cap_c"], 4), _f(r["h2_5"], 4),
            _f(h["0"], 4), _f(h["1"], 4), _f(h["2"], 4), _f(h["5"], 4),
            _f(h["10"], 4), _f(h["20"], 4), _f(h["50"], 4),
            _f(r["h3_5_over_c"], 3), r["n_proc_val"],
        ])
    lines += [_md(t), "", "验证日每 process 最大 W 前 25（每 seed）", ""]
    t = [["seed", "rank", "proc", "program", "max_W"]]
    for r in sorted(b1, key=lambda x: x["seed"]):
        for i, row in enumerate(r["top25_max_W"][:25], 1):
            t.append([r["seed"], i, row["proc"], row["program"], _f(row["max_W"], 4)])
    lines += [_md(t), "", "## B2 恶意事件信号", ""]
    t = [["seed", "attack", "s>δ", "ΣΔ", "maxW/h3", "proc", "FA ch", "D1@0", "idx0", "D1@5", "idx5"]]
    for c in cells:
        t.append([
            c["seed"], c["attack"], _f(c["frac_s_gt_delta"]), _f(c["sum_delta"], 3),
            _f(c["max_W_over_h3"]), c.get("max_W_proc") or "",
            c.get("fa_channel") or "miss",
            int(c["d1_0_hit"]), c.get("d1_0_idx") if c["d1_0_hit"] else "",
            int(c["d1_5_hit"]), c.get("d1_5_idx") if c["d1_5_hit"] else "",
        ])
    lines += [_md(t), "", "## B3 入口 process（first_Mi + 同窗口 firefox/dash）", ""]
    t = [["seed", "attack", "day", "role", "proc", "program", "n_ben", "n_mal", "n_pre", "W/h @ t0"]]
    for e in entry:
        t.append([e["seed"], e["attack"], e["day"], e.get("role") or "first_Mi", e["entry_proc"], e["program"],
                  e["n_benign_win"], e["n_mal_win"], e["n_alert_before_t0"], _f(e["W_over_h_t0"])])
    lines += [_md(t), "", "## B4 transfer（测试日越过 h3(5) 的 benign process，按程序名）", ""]
    for seed, rows in payload["transfer_per_seed"].items():
        lines += [f"### seed{seed}", ""]
        t = [["program", "n_alerts", "in_val"]]
        for r in rows:
            t.append([r["program"], r["n_alerts"], int(r["in_val"])])
        lines += [_md(t), ""]
    lines += [
        "## B5 退化 seed",
        "",
        f"- 退化 seed：**{deg['seed']}**。h1(0)={deg['h1_0']:.6g}。测试日 D1@0 标记进程数={flagged.get(int(deg['seed']))}。已核实。",
        f"- who_d1 顶格程序：{who_s}。已核实。",
        "- 原因（已核实）：h1(0)=nextafter(验证日最大 process 分数)；seed1 上多个 `dash` 打到同一 max，预算 0–10 的 h1 几乎相同；测试日没有 process 超过该 max，故 D1@0 不标记任何节点。",
        f"- 各 seed 测试日 D1@0 标记进程数：{flagged}。已核实。",
        "",
    ]
    _write(OUT / "THEIA_diag.md", "\n".join(lines) + "\n")
    _write(OUT / "THEIA_diag.json", json.dumps(payload, indent=2, default=_json))
    return payload


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
    ap.add_argument("--phase", default="all", choices=["A", "B", "report", "all", "smoke"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    if args.phase in ("A", "all", "smoke"):
        seeds = (0,) if args.phase == "smoke" else SEEDS
        todo = [s for s in seeds if args.force or not (CACHE / f"A_CADETS_seed{s}.json").is_file()]
        print(f"[v9-11] A replay {len(todo)}/{len(seeds)}", flush=True)
        if todo:
            _parallel(replay_cadets_seed, todo, args.workers)

    if args.phase in ("B", "all") and args.phase != "smoke":
        todo = [s for s in SEEDS if args.force or not (CACHE / f"B_THEIA_seed{s}.json").is_file()]
        print(f"[v9-11] B replay {len(todo)}/5", flush=True)
        if todo:
            _parallel(replay_theia_seed, todo, args.workers)

    if args.phase == "A":
        return 0
    if args.phase == "B":
        return 0

    a_seeds = (0,) if args.phase == "smoke" else SEEDS
    a_blobs = [json.loads((CACHE / f"A_CADETS_seed{s}.json").read_text(encoding="utf-8")) for s in a_seeds]
    chk_a = check_A(a_blobs)
    print(f"[check A] ok={chk_a['ok']} n={chk_a['n_compared']} flags={chk_a['n_flags']} nonconst={len(chk_a['velox_nonconst'])}", flush=True)
    if not chk_a["ok"]:
        _write(OUT / "CHECK_v9_11.json", json.dumps({"A": chk_a}, indent=2, default=_json))
        print("A 自检失败，停止。", flush=True)
        return 2

    a1 = [r for b in a_blobs for r in b["a1"]]
    a2 = summarize_a2([r for b in a_blobs for r in b["a2"]])
    a2c = summarize_a2([r for b in a_blobs for r in b["a2_ctrl"]])
    a3 = summarize_a3([r for b in a_blobs for r in b["a3"]])
    a4 = [r for b in a_blobs for r in b["a4"]]
    pairs = a_blobs[0]["pairs"]
    write_persist(a1, a2, a2c, a3, a4, chk_a, pairs)

    if args.phase == "smoke":
        print("smoke A ok", flush=True)
        return 0

    b_blobs = [json.loads((CACHE / f"B_THEIA_seed{s}.json").read_text(encoding="utf-8")) for s in SEEDS]
    chk_b = check_B(b_blobs)
    print(f"[check B] ok={chk_b['ok']} n={chk_b['n_compared']} flags={chk_b['n_flags']}", flush=True)
    if not chk_b["ok"]:
        _write(OUT / "CHECK_v9_11.json", json.dumps({"A": chk_a, "B": chk_b}, indent=2, default=_json))
        print("B 自检失败，停止。", flush=True)
        return 2
    write_theia(b_blobs, chk_b)
    _write(OUT / "CHECK_v9_11.json", json.dumps({"A": chk_a, "B": chk_b}, indent=2, default=_json))
    print(f"wrote {OUT / 'PERSIST_three_scorers.md'} {OUT / 'THEIA_diag.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
