# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Strict orthrus GT, windows, M_i, forward taint and adjacency."""

from __future__ import annotations

import ast
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from firstalarm.freeze import etypes
from firstalarm.freeze.config import ART_ROOT, CONFIG_PY, GT_ROOT
from firstalarm.freeze.db import connect_readonly, query
from firstalarm.freeze.lineage import Lineage
import numpy as np

from firstalarm.freeze.stream import EventStream
from firstalarm.freeze.timeutil import datetime_to_ns_us


@dataclass
class Attack:
    idx: int
    name: str
    gt_file: str
    day: str
    t0: int
    t1: int
    P: frozenset[int]
    G: frozenset[int]
    F: frozenset[int]
    Nflow: frozenset[int]
    uuid_missing: list[str]


@dataclass
class GroundTruth:
    dataset: str
    attacks: list[Attack]
    gt_procs: frozenset[int]
    window_0411: tuple[int, int] | None
    extra: dict = field(default_factory=dict)


def gt_path(dataset: str) -> Path:
    return ART_ROOT / dataset / "groundtruth.json"


def commented_0411(config_py: Path | None = None) -> tuple[str, str] | None:
    if config_py is None:
        import pidsmaker.config as _pc
        config_py = Path(_pc.__file__)
    text = config_py.read_text(encoding="utf-8")
    m = re.search(
        r"#\s*\[\s*\"E3-CADETS/node_Nginx_Backdoor_11\.csv\"\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\]",
        text,
    )
    if not m:
        return None
    return m.group(1), m.group(2)


def _read_gt_csv(path: Path) -> list[tuple[str, str, int | None]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for raw in csv.reader(f):
            if not raw or not raw[0].strip():
                continue
            uuid = raw[0].strip()
            typ = ""
            idx = None
            if len(raw) >= 2 and raw[1].strip():
                try:
                    d = ast.literal_eval(raw[1])
                    if isinstance(d, dict) and d:
                        typ = next(iter(d.keys()))
                except (ValueError, SyntaxError):
                    typ = ""
            if len(raw) >= 3 and raw[2].strip():
                idx = int(raw[2])
            rows.append((uuid, typ, idx))
    return rows


def build_groundtruth(dataset: str, lineage: Lineage | None = None) -> GroundTruth:
    from pidsmaker.config import DATASET_DEFAULT_CONFIG
    cfg = DATASET_DEFAULT_CONFIG[dataset]
    con, cur = connect_readonly(dataset)
    try:
        uuid2nid: dict[str, int] = {}
        nid2type: dict[int, str] = {}
        for table, typ in (
            ("subject_node_table", "subject"),
            ("file_node_table", "file"),
            ("netflow_node_table", "netflow"),
        ):
            for nid, uuid in query(cur, f"uuid {typ}", f"SELECT index_id, node_uuid FROM {table}"):
                uuid2nid[str(uuid)] = int(nid)
                nid2type[int(nid)] = typ
    finally:
        con.close()

    attacks: list[Attack] = []
    all_p: set[int] = set()
    for i, (rel, t0s, t1s) in enumerate(cfg["attack_to_time_window"]):
        t0 = datetime_to_ns_us(t0s)
        t1 = datetime_to_ns_us(t1s)
        day = t0s.split()[0]
        name = Path(rel).stem.replace("node_", "")
        rows = _read_gt_csv(GT_ROOT / rel)
        P, F, Nf, G = set(), set(), set(), set()
        missing = []
        for uuid, typ, csv_idx in rows:
            nid = uuid2nid.get(uuid)
            if nid is None:
                missing.append(uuid)
                if csv_idx is not None:
                    nid = csv_idx
                else:
                    continue
            G.add(nid)
            db_t = nid2type.get(nid, typ)
            if db_t == "subject":
                P.add(nid)
            elif db_t == "file":
                F.add(nid)
            elif db_t == "netflow":
                Nf.add(nid)
        all_p |= P
        attacks.append(
            Attack(i, name, rel, day, t0, t1, frozenset(P), frozenset(G), frozenset(F), frozenset(Nf), missing)
        )

    win = None
    extra = {}
    if dataset == "CADETS_E3":
        pair = commented_0411()
        extra["window_0411_text"] = pair
        if pair:
            win = (datetime_to_ns_us(pair[0]), datetime_to_ns_us(pair[1]))
    gt = GroundTruth(dataset, attacks, frozenset(all_p), win, extra)
    _save(gt)
    return gt


def _save(gt: GroundTruth) -> None:
    path = gt_path(gt.dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": gt.dataset,
        "window_0411": list(gt.window_0411) if gt.window_0411 else None,
        "extra": gt.extra,
        "gt_procs": sorted(gt.gt_procs),
        "attacks": [
            {
                "idx": a.idx,
                "name": a.name,
                "gt_file": a.gt_file,
                "day": a.day,
                "t0": a.t0,
                "t1": a.t1,
                "P": sorted(a.P),
                "G": sorted(a.G),
                "F": sorted(a.F),
                "Nflow": sorted(a.Nflow),
                "uuid_missing": a.uuid_missing,
            }
            for a in gt.attacks
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def load_groundtruth(dataset: str) -> GroundTruth:
    path = gt_path(dataset)
    if not path.is_file():
        return build_groundtruth(dataset)
    d = json.loads(path.read_text(encoding="utf-8"))
    attacks = [
        Attack(
            idx=a["idx"],
            name=a["name"],
            gt_file=a["gt_file"],
            day=a["day"],
            t0=int(a["t0"]),
            t1=int(a["t1"]),
            P=frozenset(a["P"]),
            G=frozenset(a["G"]),
            F=frozenset(a["F"]),
            Nflow=frozenset(a["Nflow"]),
            uuid_missing=list(a["uuid_missing"]),
        )
        for a in d["attacks"]
    ]
    win = tuple(d["window_0411"]) if d["window_0411"] else None
    return GroundTruth(d["dataset"], attacks, frozenset(d["gt_procs"]), win, d.get("extra") or {})


def mi_indices(es: EventStream, attack: Attack) -> np.ndarray:
    G = attack.G
    t0, t1 = attack.t0, attack.t1
    out = []
    for i in range(es.n):
        if t0 <= int(es.t[i]) <= t1 and int(es.src[i]) in G and int(es.dst[i]) in G:
            out.append(i)
    return np.asarray(out, dtype=np.int64)


def first_seen_before(es: EventStream, nodes: frozenset[int], t_star: int) -> float:
    if not nodes:
        return float("nan")
    seen: set[int] = set()
    for i in range(es.n):
        if int(es.t[i]) > t_star:
            break
        s, d = int(es.src[i]), int(es.dst[i])
        if s in nodes:
            seen.add(s)
        if d in nodes:
            seen.add(d)
    return len(seen) / len(nodes)


def forward_taint(es: EventStream, attack: Attack) -> set[int]:
    """T': non-P consumers of G objects that P already wrote today."""
    written: set[int] = set()
    taint: set[int] = set()
    t0, t1 = attack.t0, attack.t1
    P, G = attack.P, attack.G
    for i in range(es.n):
        et = int(es.etype[i])
        proc, obj = int(es.proc[i]), int(es.obj[i])
        if et in etypes.PRODUCER and proc in P and obj in G:
            written.add(obj)
        if t0 <= int(es.t[i]) <= t1 and et in etypes.CONSUMER and proc not in P and obj in written:
            taint.add(proc)
    return taint


def _ancestors(p: int, parent: dict[int, int], stop: frozenset[int] | None = None) -> set[int]:
    out = set()
    cur = parent.get(p)
    seen = {p}
    while cur is not None and cur not in seen:
        out.add(cur)
        if stop is not None and cur in stop:
            break
        seen.add(cur)
        cur = parent.get(cur)
    return out


def _descendants(p: int, children: dict[int, list], limit: int = 64) -> set[int]:
    out = set()
    stack = [p]
    while stack:
        u = stack.pop()
        for c, _tc in children.get(u, ()):
            if c not in out:
                out.add(c)
                if len(out) < 100000:
                    stack.append(c)
    return out


def c_both(attack: Attack, lineage: Lineage) -> set[int]:
    P = attack.P
    parent = lineage.parent
    children = lineage.children
    anc_of_p: set[int] = set()
    desc_of_p: set[int] = set()
    for p in P:
        anc_of_p |= _ancestors(p, parent)
        desc_of_p |= _descendants(p, children)
    both = set()
    cand = (anc_of_p | desc_of_p | set(parent) | set(children)) - set(P)
    for q in cand:
        has_anc = bool(_ancestors(q, parent) & P)
        has_desc = bool(_descendants(q, children) & P)
        if has_anc and has_desc:
            both.add(q)
    return both


def adjacency(es: EventStream, attack: Attack, lineage: Lineage) -> set[int]:
    """N = (creation/handover links to P_i in window ∪ C_both) \\ T'."""
    t0, t1 = attack.t0, attack.t1
    P = attack.P
    N = set()
    for c, p in lineage.parent.items():
        tc = lineage.t_c[c]
        if t0 <= tc <= t1:
            if c not in P and p in P:
                N.add(c)
            if p not in P and c in P:
                N.add(p)
    writers: dict[int, set[int]] = {}
    for i in range(es.n):
        if not (t0 <= int(es.t[i]) <= t1):
            continue
        et = int(es.etype[i])
        proc, obj = int(es.proc[i]), int(es.obj[i])
        obj_ok = int(es.src_type[i] if et in etypes.CONSUMER else es.dst_type[i]) in (1, 2)
        if et in etypes.PRODUCER and obj_ok:
            writers.setdefault(obj, set()).add(proc)
        if et in etypes.CONSUMER and obj_ok:
            ws = writers.get(obj, set())
            if proc in P:
                N |= {w for w in ws if w not in P}
            if ws & P and proc not in P:
                N.add(proc)
    N |= c_both(attack, lineage)
    N -= set(P)
    N -= forward_taint(es, attack)
    return N


def layers_for_dataset(dataset: str, seed: int, gt: GroundTruth, lineage: Lineage, load_stream_fn) -> dict:
    T_all: set[int] = set()
    N_all: set[int] = set()
    per = []
    for a in gt.attacks:
        es = load_stream_fn(dataset, seed, "test", a.day)
        T = forward_taint(es, a)
        N = adjacency(es, a, lineage)
        T_all |= T
        N_all |= N
        per.append({"idx": a.idx, "name": a.name, "T": sorted(T), "N": sorted(N)})
    return {"T": T_all, "N": N_all, "per": per}

