"""Load frozen v8 groundtruth. Never write v8. Never query DB."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from firstalarm import etypes
from firstalarm.config import V8_ART
from firstalarm.lineage import Lineage
from firstalarm.stream import EventStream


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
    return V8_ART / dataset / "groundtruth.json"


def load_groundtruth(dataset: str) -> GroundTruth:
    d = json.loads(gt_path(dataset).read_text(encoding="utf-8"))
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


def _ancestors(p: int, parent: dict[int, int]) -> set[int]:
    out = set()
    cur = parent.get(p)
    seen = {p}
    while cur is not None and cur not in seen:
        out.add(cur)
        seen.add(cur)
        cur = parent.get(cur)
    return out


def _descendants(p: int, children: dict[int, list]) -> set[int]:
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
