# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Creation edges: CADETS FORK from DB; THEIA CLONE from the stream."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from firstalarm.freeze.config import ART_ROOT, CREATION_SRC
from firstalarm.freeze.db import connect_readonly, query


@dataclass
class Lineage:
    dataset: str
    parent: dict[int, int]
    t_c: dict[int, int]
    children: dict[int, list[tuple[int, int]]]
    n_rows: int
    n_parent_eq_child: int
    n_multi: int

    def parent_of(self, child: int) -> tuple[int, int] | None:
        if child not in self.parent:
            return None
        return self.parent[child], self.t_c[child]


def lineage_path(dataset: str) -> Path:
    return ART_ROOT / dataset / "lineage.json"


def build_lineage(dataset: str) -> Lineage:
    if CREATION_SRC[dataset] != "db_fork":
        lin = Lineage(dataset, {}, {}, {}, 0, 0, 0)
        _save(lin)
        return lin
    con, cur = connect_readonly(dataset)
    try:
        rows = query(
            cur,
            "fork",
            "SELECT src_index_id, dst_index_id, timestamp_rec FROM event_table "
            "WHERE operation = 'EVENT_FORK' ORDER BY timestamp_rec, src_index_id, dst_index_id",
        )
    finally:
        con.close()
    parent: dict[int, int] = {}
    t_c: dict[int, int] = {}
    n_eq = 0
    n_multi = 0
    children: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for src, dst, ts in rows:
        p, c, tc = int(src), int(dst), int(ts)
        if p == c:
            n_eq += 1
            continue
        if c in parent:
            n_multi += 1
            if tc >= t_c[c]:
                continue
        parent[c] = p
        t_c[c] = tc
    children.clear()
    for c, p in parent.items():
        children[p].append((c, t_c[c]))
    for p in children:
        children[p].sort(key=lambda x: (x[1], x[0]))
    lin = Lineage(dataset, parent, t_c, dict(children), len(rows), n_eq, n_multi)
    _save(lin)
    return lin


def _save(lin: Lineage) -> None:
    path = lineage_path(lin.dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": lin.dataset,
        "parent": {str(k): v for k, v in lin.parent.items()},
        "t_c": {str(k): v for k, v in lin.t_c.items()},
        "n_rows": lin.n_rows,
        "n_parent_eq_child": lin.n_parent_eq_child,
        "n_multi": lin.n_multi,
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def load_lineage(dataset: str) -> Lineage:
    path = lineage_path(dataset)
    if not path.is_file():
        return build_lineage(dataset)
    d = json.loads(path.read_text(encoding="utf-8"))
    parent = {int(k): int(v) for k, v in d["parent"].items()}
    t_c = {int(k): int(v) for k, v in d["t_c"].items()}
    children: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for c, p in parent.items():
        children[p].append((c, t_c[c]))
    for p in children:
        children[p].sort(key=lambda x: (x[1], x[0]))
    return Lineage(
        dataset=dataset,
        parent=parent,
        t_c=t_c,
        children=dict(children),
        n_rows=int(d["n_rows"]),
        n_parent_eq_child=int(d["n_parent_eq_child"]),
        n_multi=int(d["n_multi"]),
    )


def clones_from_stream(t, src, dst, etype, clone_code: int) -> list[tuple[int, int, int]]:
    """Return (parent, child, t_c) from CLONE rows. src=parent, dst=child."""
    out = []
    for i in range(len(t)):
        if int(etype[i]) == clone_code:
            out.append((int(src[i]), int(dst[i]), int(t[i])))
    out.sort(key=lambda x: (x[2], x[0], x[1]))
    return out
