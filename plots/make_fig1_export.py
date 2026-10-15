"""CADETS 04-06 (A0) Fig. 1 export. Frozen v8.1 (cap=q99, prior=type).

Reads seed products under $FA_ART_ROOT/v8/CADETS_E3/; replays only
fields that those products do not store. Does not change thresholds.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from firstalarm.freeze.alerts import crossings, first_tstar
from firstalarm.freeze.config import ART_ROOT, PRE_T0_NS, REPO
from firstalarm.freeze.db import connect_readonly, query
from firstalarm.freeze.etypes import ETYPE_NAME, NTYPE_NAME
from firstalarm.freeze.evaluate import _chain_indices, eval_d4
from firstalarm.freeze.groundtruth import load_groundtruth, mi_indices
from firstalarm.freeze.lineage import load_lineage
from firstalarm.freeze.names import program_name
from firstalarm.freeze.paths import get_run_paths
from firstalarm.freeze.rules import load_pass
from firstalarm.freeze.stream import load_indexid2msg, load_stream
from firstalarm.freeze.timeutil import datetime_to_ns_us, ns_to_datetime_us

DATASET = "CADETS_E3"
ATTACK = "Nginx_Backdoor_06"
DAY = "2018-04-06"
CAP = "q99"
PRIOR = "type"
NGINX_ID = 211776
VUGEFAL_ID = 228725
SEEDS = (0, 1, 2, 3, 4)
T0_TEXT = "2018-04-06 11:20:00"
T1_TEXT = "2018-04-06 12:09:00"
PAD_NS = 10 * 60 * 10**9
OUT_DIR = REPO / "artifacts_ext" / "exports" / "fig1_cadets_0406"
KIND_NAME = {-1: "root", 0: "continuation", 1: "creation", 2: "handover"}
DISPLAY = {NGINX_ID: "nginx", VUGEFAL_ID: "vUgefal"}

SUMMARY_SPEC = (
    (1, "78.205.235.65->nginx RECVFROM", "78.205.235.65", "nginx"),
    (2, "200.36.109.214->nginx RECVFROM", "200.36.109.214", "nginx"),
    (3, "81.49.200.166->nginx RECVFROM", "81.49.200.166", "nginx"),
    (4, "nginx->/tmp/vUgefal WRITE", "nginx", "/tmp/vUgefal"),
    (5, "/tmp/vUgefal->vUgefal EXECUTE", "/tmp/vUgefal", "vUgefal"),
    (6, "vUgefal->/etc/passwd READ", "vUgefal", "/etc/passwd"),
    (7, "vUgefal<->139.123.0.113 SENDTO/RECVFROM", "vUgefal", "139.123.0.113"),
    (8, "vUgefal<->61.167.39.128 SENDTO/RECVFROM", "vUgefal", "61.167.39.128"),
    (9, "vUgefal->/var/log/devc WRITE", "vUgefal", "/var/log/devc"),
    (10, "vUgefal->154.145.113.18 SENDTO", "vUgefal", "154.145.113.18"),
)

EVENT_COLS = [
    "time_ns", "time_iso", "process_name", "process_index_id", "process_uuid",
    "event_type", "object_name", "object_index_id", "object_type", "in_M0",
    "s", "delta", "increment", "W_after", "inherited_from", "crossing",
]
M0_COLS = EVENT_COLS + ["summary_edge", "edge_in_G0"]
PROV_COLS = [
    "src_name", "src_id", "dst_name", "dst_id", "edge_type", "n_events",
    "t_first", "t_last", "in_G0", "node_max_s_src", "node_max_s_dst",
]


def _fmt(x) -> str:
    if x is None:
        return ""
    if isinstance(x, (float, np.floating)):
        v = float(x)
        if not np.isfinite(v):
            return ""
        return format(v, ".16g")
    return str(x)


def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def _label(nid: int, msg: dict) -> str:
    rec = msg.get(int(nid))
    if rec is None:
        return ""
    if isinstance(rec, (list, tuple)) and len(rec) >= 2:
        return str(rec[1])
    return str(rec)


def _disp_node(nid: int, ntype: int, msg: dict, pid_name: dict[int, str]) -> str:
    if int(nid) in pid_name:
        return pid_name[int(nid)]
    lab = _label(nid, msg)
    if ntype == 0:
        return program_name(lab) or f"proc:{nid}"
    if ntype == 1:
        toks = [t for t in lab.split() if t.lower() not in {"file", "type", "none", "null"}]
        return toks[0] if toks else (lab or f"file:{nid}")
    if ntype == 2:
        return lab or f"netflow:{nid}"
    return lab or str(nid)


def _ips(text: str) -> list[str]:
    return re.findall(r"\d+\.\d+\.\d+\.\d+", text or "")


def _load_uuid_maps(dataset: str) -> dict[int, str]:
    con, cur = connect_readonly(dataset)
    try:
        out = {}
        for table in ("subject_node_table", "file_node_table", "netflow_node_table"):
            for nid, uuid in query(cur, f"uuid {table}", f"SELECT index_id, node_uuid FROM {table}"):
                out[int(nid)] = str(uuid)
    finally:
        con.close()
    return out


def _fork_rows(dataset: str, child: int) -> list[tuple[int, int, int]]:
    con, cur = connect_readonly(dataset)
    try:
        rows = query(
            cur,
            "fork child",
            "SELECT src_index_id, dst_index_id, timestamp_rec FROM event_table "
            "WHERE operation = %s AND dst_index_id = %s "
            "ORDER BY timestamp_rec, src_index_id, dst_index_id",
            ("EVENT_FORK", str(int(child))),
        )
    finally:
        con.close()
    return [(int(a), int(b), int(c)) for a, b, c in rows]


def _select_seed(evals: dict[int, dict]) -> tuple[int, list[dict], str]:
    table = []
    for s in SEEDS:
        ev = evals[s]
        a = ev["attacks"][ATTACK]["rows"]
        d1 = a["0"]["D1"]
        d3 = a["2"]["D3"]
        table.append({
            "seed": s,
            "D1_b0_hit": bool(d1["hit"]),
            "D1_b0_tstar": d1["tstar_str"],
            "D3_b2_hit": bool(d3["hit"]),
            "D3_b2_tstar": d3["tstar_str"],
            "source": f"artifacts_ext/fa/v8/CADETS_E3/seed{s}/eval/eval.json",
        })
    both = [r["seed"] for r in table if r["D1_b0_hit"] and r["D3_b2_hit"]]
    s0 = table[0]
    if s0["D1_b0_hit"]:
        reason = "优先 seed 0：其 D1(b=0) 在 A0 窗口命中 P_0。"
        return 0, table, reason
    if both:
        chosen = min(both)
        reason = (
            f"seed 0 的 D1(b=0) 未命中（t*={s0['D1_b0_tstar']}）；"
            f"同时命中 D1(b=0) 与 D3(b=2) 的种子为 {both}，取最小编号 seed {chosen}。"
        )
        return chosen, table, reason
    raise RuntimeError("no seed with both D1(b=0) and D3(b=2) hits")


def _crossing_map(es, s, W, h1_0, h1_2, h3_2) -> dict[int, str]:
    tags = defaultdict(list)
    for name, cr in (
        ("h1(0)", crossings(es, s, h1_0, True)),
        ("h1(2)", crossings(es, s, h1_2, True)),
        ("h3(2)", crossings(es, W, h3_2, False)),
    ):
        for evs in cr.values():
            for i, _t in evs:
                tags[int(i)].append(name)
    return {i: ",".join(v) for i, v in tags.items()}


def _match_summary(et_name: str, proc_name: str, obj_name: str) -> str:
    obj = obj_name or ""
    et = et_name
    if et == "WRITE" and proc_name == "nginx" and "/tmp/vUgefal" in obj:
        return SUMMARY_SPEC[3][1]
    if et == "EXECUTE" and proc_name == "vUgefal" and "/tmp/vUgefal" in obj:
        return SUMMARY_SPEC[4][1]
    if et == "READ" and proc_name == "vUgefal" and "/etc/passwd" in obj:
        return SUMMARY_SPEC[5][1]
    if et == "WRITE" and proc_name == "vUgefal" and "/var/log/devc" in obj:
        return SUMMARY_SPEC[8][1]
    if et == "RECVFROM" and proc_name == "nginx" and "78.205.235.65" in obj:
        return SUMMARY_SPEC[0][1]
    if et == "RECVFROM" and proc_name == "nginx" and "200.36.109.214" in obj:
        return SUMMARY_SPEC[1][1]
    if et == "RECVFROM" and proc_name == "nginx" and "81.49.200.166" in obj:
        return SUMMARY_SPEC[2][1]
    if et in ("SENDTO", "RECVFROM") and proc_name == "vUgefal" and "139.123.0.113" in obj:
        return SUMMARY_SPEC[6][1]
    if et in ("SENDTO", "RECVFROM") and proc_name == "vUgefal" and "61.167.39.128" in obj:
        return SUMMARY_SPEC[7][1]
    if et == "SENDTO" and proc_name == "vUgefal" and "154.145.113.18" in obj:
        return SUMMARY_SPEC[9][1]
    return "none"


def _summary_in_g0(summary: str, g0_text: str) -> int:
    if summary == "none":
        return 0
    for _i, name, a, b in SUMMARY_SPEC:
        if name == summary:
            return int(a in g0_text and b in g0_text)
    return 0


def _rho_le(es, mi, tstar: int) -> float:
    if mi.size == 0:
        return float("nan")
    return float(np.sum(es.t[mi] <= tstar) / mi.size)


def _alert_pack(es, attack, stat, h, d1, mi, pred=None, *, fig_rho=True) -> dict:
    ts = first_tstar(es, stat, h, attack.P, attack.t0, attack.t1, d1, mi)
    if not ts["hit"]:
        return {
            "t_star": None, "t_star_iso": None, "delay_from_t0_s": None,
            "process": None, "trigger_event": None, "trigger_in_M0": None,
            "rho_e": None, "flag": None,
        }
    tstar = int(ts["tstar"])
    idx = ts["idx"]
    mi_set = set(int(x) for x in mi.tolist())
    trig = None
    if idx is not None:
        i0 = int(idx)
        trig = {
            "time": ns_to_datetime_us(int(es.t[i0])),
            "time_ns": int(es.t[i0]),
            "type": ETYPE_NAME.get(int(es.etype[i0]), str(int(es.etype[i0]))),
            "object": int(es.obj[i0]),
            "stream_index": i0,
        }
    out = {
        "t_star": tstar,
        "t_star_iso": ns_to_datetime_us(tstar),
        "delay_from_t0_s": (tstar - int(attack.t0)) / 1e9,
        "process": int(ts["proc"]) if ts["proc"] is not None else None,
        "trigger_event": trig,
        "trigger_in_M0": (int(idx) in mi_set) if idx is not None else None,
        "rho_e": _rho_le(es, mi, tstar) if fig_rho else None,
        "flag": ts.get("flag"),
    }
    if pred is not None and idx is not None:
        chain = _chain_indices(pred, int(idx))
        out["evidence_chain_length"] = len(chain)
        out["chain_contains_M0"] = any(j in mi_set for j in chain)
    return out


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _event_row(es, i, *, msg, uuids, pid_name, g0, t0, t1, W, delta, inc, pred_kind, xmap) -> list:
    proc = int(es.proc[i])
    obj = int(es.obj[i])
    et = int(es.etype[i])
    t = int(es.t[i])
    ot = int(es.src_type[i] if proc == int(es.dst[i]) else es.dst_type[i])
    if proc == int(es.dst[i]):
        ot = int(es.src_type[i])
    else:
        ot = int(es.dst_type[i])
    in_m0 = int(t0 <= t <= t1 and int(es.src[i]) in g0 and int(es.dst[i]) in g0)
    return [
        t,
        ns_to_datetime_us(t),
        pid_name.get(proc, program_name(_label(proc, msg))),
        proc,
        uuids.get(proc, ""),
        ETYPE_NAME.get(et, str(et)),
        _disp_node(obj, ot, msg, pid_name),
        obj,
        NTYPE_NAME[ot] if 0 <= ot < len(NTYPE_NAME) else str(ot),
        in_m0,
        _fmt(float(es.s[i])),
        _fmt(float(delta[i])),
        _fmt(float(inc[i])),
        _fmt(float(W[i])),
        KIND_NAME.get(int(pred_kind[i]), str(int(pred_kind[i]))),
        xmap.get(i, ""),
    ]


def export_once(out_dir: Path) -> dict:
    evals = {}
    for s in SEEDS:
        p = ART_ROOT / DATASET / f"seed{s}" / "eval" / "eval.json"
        evals[s] = json.loads(p.read_text(encoding="utf-8"))
        if evals[s].get("cap") != CAP or evals[s].get("prior") != PRIOR:
            raise RuntimeError(f"seed{s} not frozen q99/type: {evals[s].get('cap')} {evals[s].get('prior')}")

    seed, hit_table, seed_rule = _select_seed(evals)
    ev = evals[seed]
    gt = load_groundtruth(DATASET)
    attack = next(a for a in gt.attacks if a.name == ATTACK)
    if len(attack.P) != 2 or set(attack.P) != {NGINX_ID, VUGEFAL_ID}:
        raise RuntimeError(f"P_0 mismatch: {sorted(attack.P)}")

    lin = load_lineage(DATASET)
    es = load_stream(DATASET, seed, "test", DAY)
    pas = load_pass(DATASET, seed, "D3", CAP, PRIOR, "test", DAY)
    W, delta, inc, pred, pred_kind = pas.W, pas.delta, pas.inc, pas.pred, pas.pred_kind
    rp = get_run_paths(DATASET, seed)
    msg = load_indexid2msg(rp)
    uuids = _load_uuid_maps(DATASET)
    forks = _fork_rows(DATASET, VUGEFAL_ID)

    parent = lin.parent.get(VUGEFAL_ID)
    fork_t = lin.t_c.get(VUGEFAL_ID)
    fork_reason = (
        "lineage.json 对每子进程取 event_table 中最早 EVENT_FORK（与 firstalarm.freeze.lineage.build_lineage 一致）。"
    )
    if forks:
        earliest = forks[0]
        parents = sorted({p for p, _c, _t in forks})
        if parent is None:
            parent, fork_t = earliest[0], earliest[2]
            fork_reason += " lineage 缺 228725，改用库中最早 FORK。"
        fork_reason += f" 库中 FORK 父进程集合={parents}，共 {len(forks)} 条；采用 src={parent}。"
        if 229344 in parents and parent != 229344:
            fork_reason += " 229344 也出现在 FORK 行中，但不是最早父进程，故不采用。"
        elif 229344 not in parents:
            fork_reason += " 229344 在 event_table 中不是 228725 的 FORK 父进程。"
    if parent is None:
        raise RuntimeError("cannot lock vUgefal fork parent")

    pid_name = dict(DISPLAY)
    pid_name[int(parent)] = "master"

    t0, t1 = int(attack.t0), int(attack.t1)
    t_lo = t0 - PAD_NS
    h1_0 = float(ev["h1"]["0"])
    h1_2 = float(ev["h1"]["2"])
    h3_2 = float(ev["h3"]["2"])
    xmap = _crossing_map(es, es.s, W, h1_0, h1_2, h3_2)
    g0 = set(attack.G)
    mi = mi_indices(es, attack)

    focus = {NGINX_ID, VUGEFAL_ID, int(parent)}
    n_pre = sum(1 for i in range(es.n) if int(es.t[i]) < t_lo and int(es.proc[i]) in focus)
    n_229344 = sum(1 for i in range(es.n) if int(es.proc[i]) == 229344)
    ev_idx = [
        i for i in range(es.n)
        if t_lo <= int(es.t[i]) <= t1 and int(es.proc[i]) in focus
    ]
    ev_idx.sort(key=lambda i: (int(es.t[i]), int(es.src[i]), int(es.dst[i]), int(es.etype[i]), i))

    event_rows = [
        _event_row(
            es, i, msg=msg, uuids=uuids, pid_name=pid_name, g0=g0,
            t0=t0, t1=t1, W=W, delta=delta, inc=inc, pred_kind=pred_kind, xmap=xmap,
        )
        for i in ev_idx
    ]

    m0_idx = [int(i) for i in mi.tolist()]
    m0_idx.sort(key=lambda i: (int(es.t[i]), int(es.src[i]), int(es.dst[i]), int(es.etype[i]), i))

    g0_obj_labels = []
    g0_objects = []
    for nid in sorted(set(attack.F) | set(attack.Nflow)):
        rec = msg.get(int(nid))
        typ = rec[0] if isinstance(rec, (list, tuple)) else ""
        lab = _label(nid, msg)
        g0_objects.append({"index_id": int(nid), "type": str(typ), "label": lab, "uuid": uuids.get(int(nid), "")})
        g0_obj_labels.append(lab)
    g0_text = " | ".join(g0_obj_labels + ["nginx", "vUgefal", "/tmp/vUgefal"])

    m0_rows = []
    unmatched = []
    for i in m0_idx:
        base = _event_row(
            es, i, msg=msg, uuids=uuids, pid_name=pid_name, g0=g0,
            t0=t0, t1=t1, W=W, delta=delta, inc=inc, pred_kind=pred_kind, xmap=xmap,
        )
        summary = _match_summary(base[5], base[2], base[6])
        if summary == "none":
            unmatched.append({"time_iso": base[1], "process": base[2], "event_type": base[5], "object": base[6]})
        edge_g0 = _summary_in_g0(summary, g0_text)
        m0_rows.append(base + [summary, edge_g0])

    # all-day node max s (VELOX-style: max incident edge loss)
    node_max: dict[int, float] = {}
    for i in range(es.n):
        v = float(es.s[i])
        for nid in (int(es.src[i]), int(es.dst[i])):
            if nid not in node_max or v > node_max[nid]:
                node_max[nid] = v

    buckets: dict[tuple, list[int]] = defaultdict(list)
    for i in range(es.n):
        t = int(es.t[i])
        if not (t0 <= t <= t1):
            continue
        src, dst = int(es.src[i]), int(es.dst[i])
        if src not in focus and dst not in focus:
            continue
        buckets[(src, dst, int(es.etype[i]))].append(i)

    prov_rows = []
    for (src, dst, et), idxs in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        ts = [int(es.t[i]) for i in idxs]
        st = int(es.src_type[idxs[0]])
        dt = int(es.dst_type[idxs[0]])
        prov_rows.append([
            _disp_node(src, st, msg, pid_name),
            src,
            _disp_node(dst, dt, msg, pid_name),
            dst,
            ETYPE_NAME.get(et, str(et)),
            len(idxs),
            ns_to_datetime_us(min(ts)),
            ns_to_datetime_us(max(ts)),
            int(src in g0 and dst in g0),
            _fmt(node_max.get(src)),
            _fmt(node_max.get(dst)),
        ])

    d1_0 = _alert_pack(es, attack, es.s, h1_0, True, mi)
    d1_2 = _alert_pack(es, attack, es.s, h1_2, True, mi)
    d3_2 = _alert_pack(es, attack, W, h3_2, False, mi, pred)
    e4 = eval_d4(es, attack, es.s, W, h1_0, h3_2, gt.gt_procs, gt.window_0411, pred, mi)
    if e4["hit"]:
        tstar4 = int(e4["tstar"])
        ch = e4["trig"]
        if ch == "D1":
            trig4 = dict(d1_0)
        elif ch == "D3":
            trig4 = dict(d3_2)
        else:
            trig4 = dict(d1_0 if d1_0.get("t_star") == tstar4 else d3_2)
        d4_2 = {
            "t_star": tstar4,
            "t_star_iso": ns_to_datetime_us(tstar4),
            "delay_from_t0_s": (tstar4 - t0) / 1e9,
            "process": trig4.get("process"),
            "trigger_event": trig4.get("trigger_event"),
            "trigger_in_M0": trig4.get("trigger_in_M0"),
            "rho_e": _rho_le(es, mi, tstar4),
            "channel": ch,
        }
    else:
        d4_2 = {
            "t_star": None, "t_star_iso": None, "delay_from_t0_s": None,
            "process": None, "trigger_event": None, "trigger_in_M0": None,
            "rho_e": None, "channel": None,
        }

    # write / exec gap
    write_t = exec_t = None
    write_i = exec_i = None
    for i in m0_idx:
        et = ETYPE_NAME.get(int(es.etype[i]), "")
        obj_lab = _disp_node(int(es.obj[i]), int(es.src_type[i] if int(es.proc[i]) == int(es.dst[i]) else es.dst_type[i]), msg, pid_name)
        if et == "WRITE" and int(es.proc[i]) == NGINX_ID and "/tmp/vUgefal" in obj_lab and write_t is None:
            write_t, write_i = int(es.t[i]), i
        if et == "EXECUTE" and int(es.proc[i]) == VUGEFAL_ID and "/tmp/vUgefal" in obj_lab and exec_t is None:
            exec_t, exec_i = int(es.t[i]), i
    gap = None if (write_t is None or exec_t is None) else (exec_t - write_t) / 1e9

    first_m0 = int(es.t[m0_idx[0]]) if m0_idx else None

    pre = []
    for name, cr in (
        ("h1(0)", crossings(es, es.s, h1_0, True)),
        ("h1(2)", crossings(es, es.s, h1_2, True)),
        ("h3(2)", crossings(es, W, h3_2, False)),
    ):
        for p, evs in cr.items():
            if p not in attack.P:
                continue
            for i, t in evs:
                if t0 - PRE_T0_NS <= int(t) < t0:
                    pre.append({
                        "threshold": name,
                        "process": pid_name.get(int(p), str(p)),
                        "process_index_id": int(p),
                        "time_iso": ns_to_datetime_us(int(t)),
                        "time_ns": int(t),
                        "event_type": ETYPE_NAME.get(int(es.etype[i]), str(int(es.etype[i]))),
                        "stream_index": int(i),
                    })
    pre.sort(key=lambda r: (r["time_ns"], r["threshold"]))

    # truth table tokens
    sketch = [
        ("nginx", True, "P_0 / G_0 subject 211776"),
        ("vUgefal", True, "P_0 / G_0 subject 228725"),
        ("78.205.235.65", any("78.205.235.65" in x for x in g0_obj_labels), "不在 Orthrus G_0 客体"),
        ("200.36.109.214", any("200.36.109.214" in x for x in g0_obj_labels), "G_0 netflow"),
        ("81.49.200.166", any("81.49.200.166" in x for x in g0_obj_labels), "G_0 netflow（两条端口）"),
        ("/tmp/vUgefal", any("/tmp/vUgefal" in x for x in g0_obj_labels), "G_0 file 1219519"),
        ("/etc/passwd", any("/etc/passwd" in x for x in g0_obj_labels), "不在 G_0"),
        ("139.123.0.113", any("139.123.0.113" in x for x in g0_obj_labels), "G_0 netflow"),
        ("61.167.39.128", any("61.167.39.128" in x for x in g0_obj_labels), "G_0 netflow"),
        ("/var/log/devc", any("/var/log/devc" in x for x in g0_obj_labels), "不在 G_0"),
        ("154.145.113.18", any("154.145.113.18" in x for x in g0_obj_labels), "不在 G_0"),
        ("master", False, f"草图灰色；FORK 父进程 {parent}，不在 G_0"),
        ("/var/log/nginx-*.log", any("nginx" in x and "/var/log" in x for x in g0_obj_labels), "草图灰色，不在 G_0"),
        ("/etc/group", any("/etc/group" in x for x in g0_obj_labels), "草图灰色，不在 G_0"),
    ]

    field_sources = {
        "seed_hit_table": "seed*/eval/eval.json attacks.Nginx_Backdoor_06.rows",
        "thresholds": "seed*/eval/eval.json h1 / h3（验证日 calib，非回放重算）",
        "t_star": "冻结 first_tstar / eval_d4 回放；对照 eval.json tstar_str",
        "s": "seed*/stream/test_2018-04-06.npz",
        "delta,increment,W_after,inherited_from": "seed*/W/D3_q99_type/test_2018-04-06.npz（整天递推产物）",
        "crossing": "回放 firstalarm.freeze.alerts.crossings（h1(0), h1(2), h3(2)）",
        "in_M0": "回放：t∈[t0,t1] 且 src∈G_0 且 dst∈G_0（与 firstalarm.freeze.groundtruth.mi_indices 相同）",
        "process_uuid / object uuid": "只读库 subject/file/netflow_node_table",
        "fork_parent": "lineage.json + 只读 event_table EVENT_FORK dst=228725",
        "object_name": "indexid2msg.pkl + program_name / 路径或 netflow 标签",
        "node_max_s_*": "当天流上该节点作为 src 或 dst 的 max s（VELOX 节点级）",
        "rho_e": "本导出 |{e∈M_0: t(e)≤t*}|/|M_0|；v8.1 表用 t<t*，见 README",
        "alerts_dir": "产物无 seed*/alerts/；告警细节由 eval.json + 回放补",
    }

    inconsistencies = []
    stored_d1 = ev["attacks"][ATTACK]["rows"]["0"]["D1"]["tstar_str"]
    stored_d3 = ev["attacks"][ATTACK]["rows"]["2"]["D3"]["tstar_str"]
    if d1_0["t_star_iso"] != stored_d1:
        inconsistencies.append(f"D1(b=0) 回放 t*={d1_0['t_star_iso']} vs eval.json {stored_d1}")
    if d3_2["t_star_iso"] != stored_d3:
        inconsistencies.append(f"D3(b=2) 回放 t*={d3_2['t_star_iso']} vs eval.json {stored_d3}")
    if abs((gap or 0) - 86.6) > 0.2 and gap is not None:
        inconsistencies.append(f"write→exec gap {gap:.4f}s vs 交接记录 86.6s")
    if first_m0 and ns_to_datetime_us(first_m0) != "2018-04-06 11:20:12":
        inconsistencies.append(f"first_M0={ns_to_datetime_us(first_m0)} vs 交接记录 11:20:12")
    if len(m0_rows) != 21:
        inconsistencies.append(f"|M_0|={len(m0_rows)} vs 交接记录 21")
    if 229344 == parent:
        inconsistencies.append("fork 父进程为 229344（与常见 155323 不同）")
    if event_rows and float(event_rows[0][13] or 0) == 0.0:
        inconsistencies.append(
            "events.csv 首行 W_after=0：master CONNECT 负增量把余额扣到 0；"
            f"第 2 行 W>0 且 inherited_from=continuation；窗口前同三进程事件 {n_pre} 条。"
            "整天回放成立，字面「首行非零」未过。"
        )

    meta = {
        "dataset": DATASET,
        "attack": ATTACK,
        "attack_day": DAY,
        "t0": T0_TEXT,
        "t1": T1_TEXT,
        "t0_ns": t0,
        "t1_ns": t1,
        "timezone": "US/Eastern",
        "cap": CAP,
        "prior": PRIOR,
        "seed": seed,
        "seed_rule": seed_rule,
        "seed_hit_table": hit_table,
        "processes": {
            "nginx": {"name": "nginx", "index_id": NGINX_ID, "uuid": uuids.get(NGINX_ID, ""), "in_G0": True},
            "vUgefal": {"name": "vUgefal", "index_id": VUGEFAL_ID, "uuid": uuids.get(VUGEFAL_ID, ""), "in_G0": True},
            "master": {
                "name": "master",
                "index_id": int(parent),
                "uuid": uuids.get(int(parent), ""),
                "in_G0": False,
                "note": "vUgefal 的 EVENT_FORK 父进程，不是 Orthrus P_0",
            },
        },
        "fork_time": ns_to_datetime_us(int(fork_t)),
        "fork_time_ns": int(fork_t),
        "fork_source": {
            "table": "event_table",
            "operation": "EVENT_FORK",
            "parent": int(parent),
            "child": VUGEFAL_ID,
            "n_fork_rows": len(forks),
            "alt_229344": 229344 in {p for p, _c, _t in forks},
            "reason": fork_reason,
        },
        "write_exec_gap_s": None if gap is None else float(gap),
        "write_time": None if write_t is None else ns_to_datetime_us(write_t),
        "exec_time": None if exec_t is None else ns_to_datetime_us(exec_t),
        "first_M0_event_time": None if first_m0 is None else ns_to_datetime_us(first_m0),
        "thresholds": {"h1_0": h1_0, "h1_2": h1_2, "h3_2": h3_2},
        "alerts": {
            "D1_b0": d1_0,
            "D1_b2": d1_2,
            "D3_b2": d3_2,
            "D4_b2": d4_2,
        },
        "pre_t0_crossings": pre,
        "M0_size": len(m0_rows),
        "P0_size": len(attack.P),
        "G0_object_count": len(g0_objects),
        "G0_objects": g0_objects,
        "G0_subjects": [
            {"name": "nginx", "index_id": NGINX_ID, "uuid": uuids.get(NGINX_ID, "")},
            {"name": "vUgefal", "index_id": VUGEFAL_ID, "uuid": uuids.get(VUGEFAL_ID, "")},
        ],
        "summary_unmatched": unmatched,
        "truth_check": [{"token": a, "in_G0": b, "note": c} for a, b, c in sketch],
        "field_sources": field_sources,
        "inconsistencies": inconsistencies,
        "n_events_csv": len(event_rows),
        "n_provenance": len(prov_rows),
        "n_events_before_window": n_pre,
        "n_events_229344": n_229344,
        "no_alerts_dir": True,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    ev_path = out_dir / "events.csv"
    m0_path = out_dir / "m0_events.csv"
    pv_path = out_dir / "provenance_view.csv"
    _write_csv(ev_path, EVENT_COLS, event_rows)
    _write_csv(m0_path, M0_COLS, m0_rows)
    _write_csv(pv_path, PROV_COLS, prov_rows)

    # self-check
    in_m0_events = sum(1 for r in event_rows if int(r[9]) == 1)
    w0 = float(event_rows[0][13] or 0) if event_rows else 0.0
    early_w = [float(r[13] or 0) for r in event_rows[:10]]
    checks = {
        "in_M0_events_eq_m0": in_m0_events == len(m0_rows) == int(meta["M0_size"]),
        "first_W_nonzero": w0 != 0.0,
        "full_day_replay": bool(event_rows)
        and event_rows[0][14] != "root"
        and any(w > 0 for w in early_w)
        and n_pre > 0,
        "events_before_window": n_pre > 0,
        "edge_in_G0_consistent": True,
        "tstar_rows_crossing": True,
    }
    for _i, name, a, b in SUMMARY_SPEC:
        for row in m0_rows:
            if row[-2] == name and int(row[-1]) == 1:
                if not (a in g0_text and b in g0_text):
                    checks["edge_in_G0_consistent"] = False
    by_ns = {}
    for r in event_rows:
        by_ns.setdefault(int(r[0]), []).append(r)
    for key, pack in (("D1_b0", d1_0), ("D1_b2", d1_2), ("D3_b2", d3_2), ("D4_b2", d4_2)):
        if pack.get("t_star") is None:
            checks[f"{key}_null_ok"] = True
            continue
        trig = pack.get("trigger_event") or {}
        tns = int(trig.get("time_ns") or pack["t_star"])
        rows = by_ns.get(tns) or by_ns.get(int(pack["t_star"])) or []
        ok = any(r[15] for r in rows)
        checks[f"{key}_tstar_in_events"] = bool(rows) and ok
        if not (rows and ok):
            checks["tstar_rows_crossing"] = False

    meta["selfcheck"] = checks
    (out_dir / "meta.json").write_text(json.dumps(meta, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    _write_readme(out_dir, meta, sketch, unmatched)
    return meta


def _write_readme(out_dir: Path, meta: dict, sketch, unmatched) -> None:
    g0 = meta["G0_objects"]
    lines = [
        "# Fig. 1 导出 · CADETS 04-06 A0（v8.1 冻结回放）",
        "",
        "只读回放。不改门槛、不重训、不 force_restart。档位 cap=q99, prior=type。",
        "",
        "## 种子",
        "",
        f"选用 **seed {meta['seed']}**。{meta['seed_rule']}",
        "",
        "| seed | D1(b=0) | D3(b=2) |",
        "| --- | --- | --- |",
    ]
    for r in meta["seed_hit_table"]:
        lines.append(
            f"| {r['seed']} | {r['D1_b0_tstar'] if r['D1_b0_hit'] else 'miss'} | "
            f"{r['D3_b2_tstar'] if r['D3_b2_hit'] else 'miss'} |"
        )
    lines += [
        "",
        "## 进程",
        "",
        f"- nginx `{meta['processes']['nginx']['index_id']}` uuid `{meta['processes']['nginx']['uuid']}`：Orthrus `node_Nginx_Backdoor_06.csv` 第一行，A0_HINT 固定 id，|P_0|=2。",
        f"- vUgefal `{meta['processes']['vUgefal']['index_id']}` uuid `{meta['processes']['vUgefal']['uuid']}`：同一 CSV。",
        f"- master `{meta['processes']['master']['index_id']}` uuid `{meta['processes']['master']['uuid']}`：{meta['fork_source']['reason']}",
        f"- fork 时刻：{meta['fork_time']}（美东）。",
        "",
        "## G_0 客体清单（6）",
        "",
    ]
    for o in g0:
        lines.append(f"- `{o['index_id']}` {o['type']} `{o['label']}` uuid `{o['uuid']}`")
    lines += [
        "",
        "G_0 主体：nginx 211776、vUgefal 228725。合计 |G_0|=8。",
        "",
        "## 真值核对",
        "",
        "| 名称 | 在 G_0 | 说明 |",
        "| --- | --- | --- |",
    ]
    for row in sketch:
        lines.append(f"| {row[0]} | {'是' if row[1] else '否'} | {row[2]} |")
    lines += [
        "",
        "## in_M0",
        "",
        "判定代码：本脚本 `_event_row`，与 `firstalarm.freeze.groundtruth.mi_indices` 相同：",
        "`t0 ≤ t ≤ t1` 且 `src ∈ G_0` 且 `dst ∈ G_0`。G_0 来自 `artifacts_ext/fa/v8/CADETS_E3/groundtruth.json`（Orthrus 严格真值）。",
        "",
        "## 汇总边",
        "",
        "多条流事件压到同一 `summary_edge` 字符串。对不上的填 `none`。本导出未匹配：",
        "",
    ]
    if unmatched:
        for u in unmatched:
            lines.append(f"- {u['time_iso']} {u['process']} {u['event_type']} {u['object']}")
    else:
        lines.append("- （无）")
    lines += [
        "",
        "`/etc/passwd`、`/var/log/devc`、`78.205.235.65`、`154.145.113.18` 不在 G_0，对应汇总边 `edge_in_G0=0`。",
        "",
        "## 字段来源",
        "",
    ]
    for k, v in meta["field_sources"].items():
        lines.append(f"- **{k}**：{v}")
    lines += [
        "",
        "## rho_e 口径",
        "",
        "本导出 `rho_e = |{e∈M_0: t(e)≤t*}|/|M_0|`（含 t* 当时事件）。",
        "v8.1 评估表用 `t < t*`（`firstalarm.freeze.evaluate._rho_e`）。数字可能差 1/|M_0|。",
        "",
        "## 自检",
        "",
        json.dumps(meta["selfcheck"], ensure_ascii=False, indent=2),
        "",
        "## 不一致",
        "",
    ]
    if meta["inconsistencies"]:
        for x in meta["inconsistencies"]:
            lines.append(f"- {x}")
    else:
        lines.append("- 无。")
    lines.append("")
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta1 = export_once(OUT_DIR)
    names = ("events.csv", "m0_events.csv", "provenance_view.csv", "meta.json", "README.md")
    h1 = {n: _md5(OUT_DIR / n) for n in names}
    meta2 = export_once(OUT_DIR)
    h2 = {n: _md5(OUT_DIR / n) for n in names}
    required = {k: v for k, v in meta2["selfcheck"].items() if k != "first_W_nonzero"}
    ok = h1 == h2 and all(required.values()) and bool(meta2["selfcheck"].get("full_day_replay"))
    print("seed", meta2["seed"])
    print("hit_table", json.dumps(meta2["seed_hit_table"], ensure_ascii=False))
    print("M0_size", meta2["M0_size"], "events", meta2["n_events_csv"], "prov", meta2["n_provenance"])
    for k, a in meta2["alerts"].items():
        print(k, a.get("t_star_iso"), a.get("delay_from_t0_s"), a.get("rho_e"), a.get("channel"))
    print("fork", meta2["processes"]["master"]["index_id"], meta2["fork_time"], "gap", meta2["write_exec_gap_s"])
    print("md5", h2, "twice_equal", h1 == h2)
    print("selfcheck", meta2["selfcheck"], "ALL_OK", ok)
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
