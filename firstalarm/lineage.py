"""Load frozen v8 lineage. Never write v8. Never query DB."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from firstalarm.config import V8_ART


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
    return V8_ART / dataset / "lineage.json"


def load_lineage(dataset: str) -> Lineage:
    path = lineage_path(dataset)
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
