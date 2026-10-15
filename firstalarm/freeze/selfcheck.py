# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""I: T-toy, hand example, D1 vs pth, bitwise determinism."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import torch

from firstalarm.freeze import etypes
from firstalarm.freeze.alerts import crossings
from firstalarm.freeze.calibrate import calib_from_stat
from firstalarm.freeze.config import ART_ROOT, TEST_DATES, VAL_DATES
from firstalarm.freeze.etypes import CLONE, READ, WRITE
from firstalarm.freeze.lineage import Lineage
from firstalarm.freeze.names import program_name
from firstalarm.freeze.paths import get_run_paths, result_pth_path
from firstalarm.freeze.rent import Priors
from firstalarm.freeze.rules import run_d1, run_d2, run_d3
from firstalarm.freeze.stream import EventStream, load_indexid2msg, load_stream, stream_exists
from firstalarm.freeze.timeutil import datetime_to_ns_us, ns_to_day_us


def _es(rows, dataset="CADETS_E3", day="2018-04-10") -> EventStream:
    """rows: (t, etype, src, dst, s, src_type, dst_type, proc, obj, kind)."""
    t = np.array([r[0] for r in rows], dtype=np.int64)
    et = np.array([r[1] for r in rows], dtype=np.int16)
    src = np.array([r[2] for r in rows], dtype=np.int64)
    dst = np.array([r[3] for r in rows], dtype=np.int64)
    s = np.array([r[4] for r in rows], dtype=np.float64)
    st = np.array([r[5] for r in rows], dtype=np.int8)
    dt = np.array([r[6] for r in rows], dtype=np.int8)
    proc = np.array([r[7] for r in rows], dtype=np.int64)
    obj = np.array([r[8] for r in rows], dtype=np.int64)
    kind = np.array([r[9] for r in rows], dtype=object)
    return EventStream(
        dataset=dataset, seed=0, split="toy", day=day,
        t=t, src=src, dst=dst, etype=et, s=s,
        proc=proc, obj=obj, src_type=st, dst_type=dt,
        proc_type=np.zeros(len(rows), dtype=np.int8),
        kind=kind, meta={"n_raw": len(rows), "n_keep": len(rows)},
    )


def _priors(delta: float, mode: str = "type") -> Priors:
    return Priors(mode, {}, {}, float(delta), {}, {}, None, 0.0)


def t_toy() -> dict:
    t0 = datetime_to_ns_us("2018-04-10 00:00:01")
    step = 10**9
    parent, child, fobj = 10, 20, 100
    rows = []
    # parent 3 writes, s=3
    for k in range(3):
        t = t0 + k * step
        rows.append((t, WRITE, parent, fobj, 3.0, 0, 1, parent, fobj, "parent"))
    tc = t0 + 2 * step + 1  # after parent W reaches 6
    for k in range(5):
        t = t0 + (3 + k) * step
        rows.append((t, WRITE, child, fobj, 3.0, 0, 1, child, fobj, "child"))
    es = _es(rows)
    lin = Lineage("CADETS_E3", {child: parent}, {child: tc}, {parent: [(child, tc)]}, 1, 0, 0)
    pr = _priors(1.0)
    h = 10.0
    s = run_d1(es)
    p2 = run_d2(es, pr, None, lin)
    p3 = run_d3(es, pr, None, lin, links=True)
    d1_idx = [i for i in range(es.n) if int(es.proc[i]) == child and float(s[i]) >= h]
    cr2 = crossings(es, p2.W, h, False)
    cr3 = crossings(es, p3.W, h, False)
    c2 = cr2.get(child, [])
    c3 = cr3.get(child, [])
    # child events are indices 3..7
    ok = (len(d1_idx) == 0) and (len(c2) == 1 and c2[0][0] == 7) and (len(c3) == 1 and c3[0][0] == 4)
    return {
        "name": "T-toy",
        "ok": bool(ok),
        "D1_child_alerts": d1_idx,
        "D2_child_first_i": None if not c2 else c2[0][0],
        "D3_child_first_i": None if not c3 else c3[0][0],
        "W2_child": [float(p2.W[i]) for i in range(3, 8)],
        "W3_child": [float(p3.W[i]) for i in range(3, 8)],
        "W_parent": [float(p3.W[i]) for i in range(3)],
        "expect": "D1 none; D2 i=7 (5th child); D3 i=4 (2nd child); parent W 2,4,6",
    }


def hand_example() -> dict:
    t0 = datetime_to_ns_us("2018-04-06 11:21:00")
    step = 10**9
    nginx, vug, fobj = 1, 2, 100
    rows = []
    for k in range(5):
        t = t0 + k * step
        rows.append((t, WRITE, nginx, fobj, 10.0, 0, 1, nginx, fobj, "nginx"))
    t = t0 + 5 * step
    rows.append((t, READ, fobj, vug, 4.0, 1, 0, vug, fobj, "vugefal"))
    es = _es(rows, day="2018-04-06")
    pr = _priors(2.0)
    p3 = run_d3(es, pr, 6.0, None, links=True)
    want_ng = [6.0, 12.0, 18.0, 24.0, 30.0]
    want_vu = 32.0
    got_ng = [float(p3.W[i]) for i in range(5)]
    got_vu = float(p3.W[5])
    ok = np.allclose(got_ng, want_ng, rtol=0, atol=0) and got_vu == want_vu
    return {
        "name": "hand-nginx-vUgefal",
        "ok": bool(ok),
        "W_nginx": got_ng,
        "W_vUgefal": got_vu,
        "expect_nginx": want_ng,
        "expect_vUgefal": want_vu,
        "pred_kind_last": int(p3.pred_kind[5]),
        "inc": [float(p3.inc[i]) for i in range(6)],
    }


def _sha(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def determinism_toy() -> dict:
    a = t_toy()
    b = t_toy()
    h = hand_example()
    h2 = hand_example()
    ok = a["W3_child"] == b["W3_child"] and h["W_nginx"] == h2["W_nginx"] and h["W_vUgefal"] == h2["W_vUgefal"]
    return {"name": "determinism-toy", "ok": bool(ok)}


def d1_vs_pth(dataset: str, seed: int) -> dict:
    from firstalarm.freeze.etypes import NTYPE
    from firstalarm.freeze.paths import get_run_paths

    rp = get_run_paths(dataset, seed)
    val_day = VAL_DATES[dataset]
    esv = load_stream(dataset, seed, "val", val_day)
    hmap = calib_from_stat(esv, esv.s)
    h0 = hmap[0]
    A: set[int] = set()
    clone_dst: set[int] = set()
    for day in TEST_DATES[dataset]:
        if not stream_exists(dataset, seed, "test", day):
            continue
        es = load_stream(dataset, seed, "test", day)
        cr = crossings(es, es.s, h0, True)
        A |= set(cr)
        for i in range(es.n):
            if int(es.etype[i]) == CLONE:
                clone_dst.add(int(es.dst[i]))
    msg = load_indexid2msg(rp)
    pth = torch.load(result_pth_path(rp), map_location="cpu")
    V = set()
    n_pos = 0
    for nid, rec in pth.items():
        nid = int(nid)
        if not rec.get("y_hat"):
            continue
        n_pos += 1
        info = msg.get(nid)
        typ = info[0] if isinstance(info, (list, tuple)) else None
        if typ == "subject":
            V.add(nid)
    v_minus = V - A
    a_minus = A - V
    unexplained = {p for p in v_minus if p not in clone_dst}
    ok = len(a_minus) == 0 and len(unexplained) == 0
    return {
        "name": f"D1-pth {dataset} seed{seed}",
        "ok": bool(ok),
        "h1_0": h0,
        "|A|": len(A),
        "|V|": len(V),
        "|V-A|": len(v_minus),
        "|A-V|": len(a_minus),
        "V-A_clone": sorted(v_minus & clone_dst)[:20],
        "V-A_unexplained": sorted(unexplained)[:20],
        "A-V_sample": sorted(a_minus)[:20],
        "n_yhat": n_pos,
    }


def determinism_real(dataset: str, seed: int) -> dict:
    from firstalarm.freeze.lineage import load_lineage
    from firstalarm.freeze.rent import build_priors, cap_q99, delta_on_stream

    val = load_stream(dataset, seed, "val", VAL_DATES[dataset])
    lin = load_lineage(dataset)
    pr = build_priors(val, "kind")
    dlt = delta_on_stream(val, pr)
    c, _ = cap_q99(val, dlt)
    p1 = run_d3(val, pr, c, lin, True)
    p2 = run_d3(val, pr, c, lin, True)
    ok = np.array_equal(p1.W, p2.W) and np.array_equal(p1.pred, p2.pred) and np.array_equal(p1.pred_kind, p2.pred_kind)
    return {
        "name": f"determinism-real {dataset} seed{seed}",
        "ok": bool(ok),
        "W_sha": _sha(p1.W),
    }


def run_selfcheck(dataset: str = "CADETS_E3", seeds=None, need_real: bool = True) -> dict:
    seeds = list(seeds if seeds is not None else (0, 1, 2, 3, 4))
    rows = [t_toy(), hand_example(), determinism_toy()]
    if need_real:
        for k in seeds:
            if stream_exists(dataset, k, "val", VAL_DATES[dataset]):
                rows.append(d1_vs_pth(dataset, k))
                rows.append(determinism_real(dataset, k))
    ok = all(r["ok"] for r in rows)
    return {"ok": ok, "checks": rows}


def format_selfcheck(res: dict) -> str:
    lines = ["# v8 self-check", "", f"ALL_PASS={res['ok']}", ""]
    for r in res["checks"]:
        lines.append(f"## {r['name']}: {'PASS' if r['ok'] else 'FAIL'}")
        for k, v in r.items():
            if k in ("name", "ok"):
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--host", default="CADETS_E3", choices=("CADETS_E3", "THEIA_E3"))
    args = ap.parse_args()
    res = run_selfcheck(dataset=args.host, need_real=args.real)
    print(format_selfcheck(res))
    raise SystemExit(0 if res["ok"] else 1)
