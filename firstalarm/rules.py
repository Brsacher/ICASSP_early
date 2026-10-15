"""D1 / D2 / D3 single-pass recurrence (v9 snapshot + rearm)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from firstalarm import etypes
from firstalarm.config import ART_ROOT, CREATION_SRC
from firstalarm.lineage import Lineage
from firstalarm.rent import Priors, clip_inc, delta_on_stream
from firstalarm.stream import EventStream
from firstalarm.timeutil import ns_to_day_us


@dataclass
class Pass:
    W: np.ndarray
    W_mem: np.ndarray
    pred: np.ndarray
    pred_kind: np.ndarray
    inc: np.ndarray
    delta: np.ndarray
    stats: dict
    alerts: dict[int, list[tuple[int, int]]] = field(default_factory=dict)


def run_d1(es: EventStream) -> np.ndarray:
    return es.s.astype(np.float64)


def _kind_by_proc(es: EventStream) -> dict[int, str]:
    out: dict[int, str] = {}
    for i in range(es.n):
        p = int(es.proc[i])
        if p not in out:
            out[p] = str(es.kind[i])
    return out


def _forks_cadets(es: EventStream, lineage: Lineage) -> list[tuple[int, int, int]]:
    if not lineage.parent:
        return []
    kids = np.fromiter(lineage.parent.keys(), dtype=np.int64)
    tcs = np.fromiter((lineage.t_c[int(c)] for c in kids), dtype=np.int64)
    days = ns_to_day_us(tcs)
    best: dict[int, tuple[int, int, int]] = {}
    for c, d, tc in zip(kids.tolist(), days.tolist(), tcs.tolist()):
        if str(d) != es.day:
            continue
        p = lineage.parent[int(c)]
        if p == int(c):
            continue
        prev = best.get(int(c))
        if prev is None or int(tc) < prev[2]:
            best[int(c)] = (p, int(c), int(tc))
    return sorted(best.values(), key=lambda x: (x[2], x[0], x[1]))


def _parent_w_at(hist: list[tuple[int, float, int]], tc: int) -> tuple[float, int]:
    """Parent W at last event with t<=tc. Callers must not have recorded the creation event yet."""
    w, idx = 0.0, -1
    for tt, ww, ii in hist:
        if tt <= tc:
            w, idx = ww, ii
        else:
            break
    return w, idx


def run_d3(
    es: EventStream,
    pr: Priors,
    cap_c: float | None,
    lineage: Lineage | None,
    links: bool,
    delta: np.ndarray | None = None,
    rearm: str = "below",
    h: float | None = None,
) -> Pass:
    if delta is None:
        delta = delta_on_stream(es, pr)
    inc = clip_inc(es.s.astype(np.float64) - delta, cap_c)
    n = es.n
    W = np.zeros(n, dtype=np.float64)
    W_mem = np.zeros(n, dtype=np.float64)
    pred = np.full(n, -1, dtype=np.int64)
    pred_kind = np.full(n, -1, dtype=np.int8)
    alerts: dict[int, list[tuple[int, int]]] = {}

    last_w: dict[int, float] = {}
    last_i: dict[int, int] = {}
    last_ev: dict[int, tuple[int, float, int]] = {}
    prev_ev: dict[int, tuple[int, float, int]] = {}
    seen: set[int] = set()
    reroot: set[int] = set()
    kinds = _kind_by_proc(es)
    use_reset = rearm in ("reset", "fir") and h is not None
    h_val = float(h) if h is not None else 0.0

    use_db = links and CREATION_SRC[es.dataset] == "db_fork"
    use_cl = links and CREATION_SRC[es.dataset] == "stream_clone"
    forks = _forks_cadets(es, lineage) if (use_db and lineage is not None) else []
    fi = 0
    n_c_parent: dict[int, int] = {}
    snap_w: dict[int, float] = {}
    snap_idx: dict[int, int] = {}
    n_c_child: dict[int, int] = {}
    cpi_child: dict[int, int] = {}
    pat_c: dict[tuple[str, str], int] = {}

    def apply_fork(p: int, c: int, tc: int) -> None:
        if c in snap_w:
            return
        hist = []
        if p in prev_ev:
            hist.append(prev_ev[p])
        if p in last_ev:
            hist.append(last_ev[p])
        pw, pidx = _parent_w_at(hist, tc)
        snap_w[c] = pw
        snap_idx[c] = pidx
        n_c_parent[p] = n_c_parent.get(p, 0) + 1
        n_c_child[c] = n_c_parent[p]
        pk = (kinds.get(p, "unknown"), kinds.get(c, "unknown"))
        cpi_child[c] = pat_c.get(pk, 0)
        pat_c[pk] = pat_c.get(pk, 0) + 1

    def flush(upto: int) -> None:
        nonlocal fi
        while fi < len(forks) and forks[fi][2] <= upto:
            p, c, tc = forks[fi]
            apply_fork(p, c, tc)
            fi += 1

    writers: dict[int, list] = {}
    readers: dict[int, set[int]] = {}
    pat_h: dict[tuple[str, str, int], int] = {}
    n_create = n_hand = n_prev = n_root = 0
    n_eff = n_link = 0
    n_alert = 0

    for i in range(n):
        proc = int(es.proc[i])
        obj = int(es.obj[i])
        et = int(es.etype[i])
        kind = str(es.kind[i])
        t = int(es.t[i])
        if use_db:
            flush(t - 1)

        first = proc not in seen
        restart = proc in reroot
        if restart:
            reroot.discard(proc)
            W_prev = last_w.get(proc, 0.0)
            i_prev = -1
        else:
            W_prev = last_w.get(proc, 0.0)
            i_prev = last_i.get(proc, -1)

        cand_c = 0.0
        pred_c = -1
        coef_c = 0.0
        if links and first and proc in snap_w:
            nc = max(int(n_c_child.get(proc, 1)), 1)
            cpi = int(cpi_child.get(proc, 0))
            coef_c = (1.0 / nc) * (1.0 / (1.0 + cpi))
            cand_c = float(snap_w[proc]) * coef_c
            pred_c = int(snap_idx[proc])

        cand_h = 0.0
        pred_h = -1
        coef_h = 0.0
        ot = int(es.src_type[i]) if et in etypes.CONSUMER else int(es.dst_type[i])
        if links and et in etypes.CONSUMER and ot in (1, 2):
            chosen = None
            for item in writers.get(obj, []):
                if int(item[1]) != proc:
                    chosen = item
                    break
            if chosen is not None:
                rd = readers.setdefault(obj, set())
                rd.add(proc)
                nr = max(len(rd), 1)
                pk = (kinds.get(int(chosen[1]), "unknown"), kind, ot)
                cpi = pat_h.get(pk, 0)
                coef_h = (1.0 / nr) * (1.0 / (1.0 + cpi))
                cand_h = float(chosen[0]) * coef_h
                pred_h = int(chosen[2])
                pat_h[pk] = cpi + 1

        best = W_prev
        kind_i = 0 if (not first and not restart) else -1
        pred_i = i_prev
        used = 0.0
        if cand_c > best:
            best = cand_c
            kind_i = 1
            pred_i = pred_c
            used = coef_c
        if cand_h > best:
            best = cand_h
            kind_i = 2
            pred_i = pred_h
            used = coef_h

        w = max(0.0, best + float(inc[i]))
        W[i] = w
        pred[i] = pred_i
        pred_kind[i] = kind_i
        if kind_i == -1:
            n_root += 1
        elif kind_i == 0:
            n_prev += 1
        elif kind_i == 1:
            n_create += 1
            n_link += 1
            n_eff += int(used >= 0.5)
        else:
            n_hand += 1
            n_link += 1
            n_eff += int(used >= 0.5)

        mem = w
        if use_reset and int(es.proc_type[i]) == 0 and W_prev < h_val and w >= h_val:
            alerts.setdefault(proc, []).append((i, t))
            n_alert += 1
            mem = 0.0 if rearm == "reset" else 0.5 * h_val
            reroot.add(proc)
        W_mem[i] = mem
        # THEIA CLONE snapshot before recording this event, so child does not inherit the CLONE Δ.
        if use_cl and et == etypes.CLONE:
            child = int(es.dst[i])
            if child != proc:
                apply_fork(proc, child, t)
        last_w[proc] = mem
        last_i[proc] = i
        prev = last_ev.get(proc)
        if prev is not None and prev[0] < t:
            prev_ev[proc] = prev
        last_ev[proc] = (t, mem, i)
        seen.add(proc)
        if use_db:
            flush(t)

        if links and et in etypes.PRODUCER and ot in (1, 2):
            lst = writers.get(obj)
            if lst is None:
                writers[obj] = [[mem, proc, i]]
            else:
                found = False
                for item in lst:
                    if int(item[1]) == proc:
                        if mem > float(item[0]):
                            item[0] = mem
                            item[2] = i
                        found = True
                        break
                if not found:
                    lst.append([mem, proc, i])
                lst.sort(key=lambda z: (-float(z[0]), int(z[2])))
                writers[obj] = lst[:2]

    stats = {
        "n": n,
        "n_root": n_root,
        "n_prev": n_prev,
        "n_creation": n_create,
        "n_handover": n_hand,
        "n_link_steps": n_link,
        "n_effective_inherit": n_eff,
        "density": (n_eff / n) if n else 0.0,
        "links": bool(links),
        "cap_c": None if cap_c is None else float(cap_c),
        "prior": pr.prior_mode,
        "rearm": rearm,
        "h": None if h is None else float(h),
        "n_alert": n_alert,
    }
    return Pass(W, W_mem, pred, pred_kind, inc, delta, stats, alerts)


def run_d2(
    es: EventStream,
    pr: Priors,
    cap_c: float | None,
    lineage: Lineage | None,
    delta: np.ndarray | None = None,
    rearm: str = "below",
    h: float | None = None,
) -> Pass:
    return run_d3(es, pr, cap_c, lineage, links=False, delta=delta, rearm=rearm, h=h)


def pass_path(
    dataset: str,
    seed: int,
    rule: str,
    cap: str,
    prior: str,
    split: str,
    day: str,
    rearm: str = "below",
    b: int | None = None,
) -> Path:
    if rearm == "below" or b is None:
        tag = f"{rule}_{cap}_{prior}_{rearm}"
    else:
        tag = f"{rule}_{cap}_{prior}_{rearm}_b{b}"
    return ART_ROOT / dataset / f"seed{seed}" / "W" / tag / f"{split}_{day}.npz"


def save_pass(
    dataset: str,
    seed: int,
    rule: str,
    cap: str,
    prior: str,
    split: str,
    day: str,
    p: Pass,
    rearm: str = "below",
    b: int | None = None,
) -> Path:
    path = pass_path(dataset, seed, rule, cap, prior, split, day, rearm, b)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, W=p.W, W_mem=p.W_mem, pred=p.pred, pred_kind=p.pred_kind, inc=p.inc, delta=p.delta)
    extra = dict(p.stats)
    extra["alerts"] = {str(k): v for k, v in p.alerts.items()}
    path.with_suffix(".stats.json").write_text(json.dumps(extra, sort_keys=True), encoding="utf-8")
    return path


def pass_exists(
    dataset: str,
    seed: int,
    rule: str,
    cap: str,
    prior: str,
    split: str,
    day: str,
    rearm: str = "below",
    b: int | None = None,
) -> bool:
    return pass_path(dataset, seed, rule, cap, prior, split, day, rearm, b).is_file()


def load_pass(
    dataset: str,
    seed: int,
    rule: str,
    cap: str,
    prior: str,
    split: str,
    day: str,
    rearm: str = "below",
    b: int | None = None,
) -> Pass:
    path = pass_path(dataset, seed, rule, cap, prior, split, day, rearm, b)
    z = np.load(path)
    raw = json.loads(path.with_suffix(".stats.json").read_text(encoding="utf-8"))
    alerts = {int(k): [tuple(x) for x in v] for k, v in (raw.pop("alerts", {}) or {}).items()}
    wmem = z["W_mem"] if "W_mem" in z.files else z["W"]
    return Pass(z["W"], wmem, z["pred"], z["pred_kind"], z["inc"], z["delta"], raw, alerts)
