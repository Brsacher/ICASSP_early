"""Align Kairos / ORTHRUS epoch-11 losses onto VELOX keys and v8 EventStreams.

Read-only on velox_seeds / kairos_seeds / orthrus_seeds / fa/v8.
Writes only under the current scorer art root (v9_kairos or v9_orthrus).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from firstalarm.config import TEST_DATES, VAL_DATES
from firstalarm.kairos_config import DATASET, assert_write_path, get_scorer, spec
from firstalarm.kairos_paths import csvs, get_scorer_paths, get_velox_paths
from firstalarm.stream import EventStream, load_stream
from firstalarm.timeutil import ns_to_day_us

COLS = ["loss", "srcnode", "dstnode", "time", "edge_type"]
DTYPE = {
    "loss": np.float64,
    "srcnode": np.int64,
    "dstnode": np.int64,
    "time": np.int64,
    "edge_type": np.int64,
}


def _read_csv(path) -> pd.DataFrame:
    return pd.read_csv(path, usecols=COLS, dtype=DTYPE)


def _keys(df: pd.DataFrame) -> np.ndarray:
    return np.ascontiguousarray(
        np.stack(
            [
                df["srcnode"].to_numpy(np.int64),
                df["dstnode"].to_numpy(np.int64),
                df["time"].to_numpy(np.int64),
                df["edge_type"].to_numpy(np.int64),
            ],
            axis=1,
        )
    )


def pack_keys(src, dst, t, et) -> np.ndarray:
    return np.ascontiguousarray(
        np.stack(
            [
                np.asarray(src, dtype=np.int64),
                np.asarray(dst, dtype=np.int64),
                np.asarray(t, dtype=np.int64),
                np.asarray(et, dtype=np.int64),
            ],
            axis=1,
        )
    )


def sorted_keys(keys: np.ndarray) -> np.ndarray:
    order = np.lexsort((keys[:, 3], keys[:, 2], keys[:, 1], keys[:, 0]))
    return keys[order]


def dup_row_frac(keys: np.ndarray) -> float:
    if keys.size == 0:
        return 0.0
    sk = sorted_keys(keys)
    # run-length
    change = np.empty(len(sk), dtype=bool)
    change[0] = True
    change[1:] = np.any(sk[1:] != sk[:-1], axis=1)
    starts = np.flatnonzero(change)
    counts = np.diff(np.append(starts, len(sk)))
    return float(counts[counts > 1].sum()) / float(len(sk))


def align_window(k_df: pd.DataFrame, v_df: pd.DataFrame) -> tuple[np.ndarray, int, str]:
    """Return scorer loss in VELOX row order. unmatched must be 0."""
    if len(k_df) != len(v_df):
        raise RuntimeError(f"window row count k={len(k_df)} v={len(v_df)}")
    kk, vk = _keys(k_df), _keys(v_df)
    if np.array_equal(kk, vk):
        return k_df["loss"].to_numpy(np.float64), 0, "position"
    buckets: dict[tuple, list[float]] = defaultdict(list)
    for i in range(len(k_df)):
        buckets[tuple(kk[i])].append(float(k_df["loss"].iat[i]))
    occ: dict[tuple, int] = defaultdict(int)
    out = np.empty(len(v_df), dtype=np.float64)
    unmatched = 0
    for i in range(len(v_df)):
        key = tuple(vk[i])
        j = occ[key]
        occ[key] = j + 1
        lst = buckets.get(key)
        if lst is None or j >= len(lst):
            unmatched += 1
            out[i] = np.nan
        else:
            out[i] = lst[j]
    return out, unmatched, "key_occ"


@dataclass
class DayAlign:
    src: np.ndarray
    dst: np.ndarray
    t: np.ndarray
    et: np.ndarray
    s_k: np.ndarray
    s_v: np.ndarray
    mode: str
    unmatched: int
    n: int
    n_dup_frac_k: float
    n_dup_frac_v: float
    multi_eq: bool


_ALIGN: dict[tuple[int, str], dict[str, DayAlign]] = {}


def clear_align_cache() -> None:
    _ALIGN.clear()


def align_split(seed: int, split: str) -> dict[str, DayAlign]:
    """Read each window CSV once; return DayAlign per calendar day."""
    key = (get_scorer(), int(seed), split)
    if key in _ALIGN:
        return _ALIGN[key]
    kr = get_scorer_paths(seed)
    vr = get_velox_paths(seed)
    k_files = {p.name: p for p in csvs(kr, split)}
    v_files = {p.name: p for p in csvs(vr, split)}
    if set(k_files) != set(v_files):
        only_k = sorted(set(k_files) - set(v_files))[:5]
        only_v = sorted(set(v_files) - set(k_files))[:5]
        raise RuntimeError(f"window names differ seed{seed} {split}: only_k={only_k} only_v={only_v}")
    acc: dict[str, dict] = defaultdict(lambda: {
        "src": [], "dst": [], "t": [], "et": [], "sk": [], "sv": [],
        "ksrc": [], "kdst": [], "kt": [], "ket": [],
        "um": 0, "modes": Counter(),
    })
    names = sorted(v_files, key=lambda n: int("".join(ch for ch in n if ch.isdigit()) or "0"))
    for name in names:
        k_df = _read_csv(k_files[name])
        v_df = _read_csv(v_files[name])
        kd = ns_to_day_us(k_df["time"].to_numpy(np.int64))
        vd = ns_to_day_us(v_df["time"].to_numpy(np.int64))
        for day in set(kd.tolist()) | set(vd.tolist()):
            k_sub = k_df.loc[kd == day].reset_index(drop=True)
            v_sub = v_df.loc[vd == day].reset_index(drop=True)
            if len(k_sub) == 0 and len(v_sub) == 0:
                continue
            loss_k, um, mode = align_window(k_sub, v_sub)
            b = acc[day]
            b["src"].append(v_sub["srcnode"].to_numpy(np.int64))
            b["dst"].append(v_sub["dstnode"].to_numpy(np.int64))
            b["t"].append(v_sub["time"].to_numpy(np.int64))
            b["et"].append(v_sub["edge_type"].to_numpy(np.int64))
            b["sk"].append(loss_k)
            b["sv"].append(v_sub["loss"].to_numpy(np.float64))
            b["ksrc"].append(k_sub["srcnode"].to_numpy(np.int64))
            b["kdst"].append(k_sub["dstnode"].to_numpy(np.int64))
            b["kt"].append(k_sub["time"].to_numpy(np.int64))
            b["ket"].append(k_sub["edge_type"].to_numpy(np.int64))
            b["um"] += um
            b["modes"][mode] += 1
    out: dict[str, DayAlign] = {}
    for day, b in acc.items():
        if not b["src"]:
            continue
        src = np.concatenate(b["src"])
        dst = np.concatenate(b["dst"])
        t = np.concatenate(b["t"])
        et = np.concatenate(b["et"])
        s_k = np.concatenate(b["sk"])
        s_v = np.concatenate(b["sv"])
        kk_v = pack_keys(src, dst, t, et)
        kk_k = pack_keys(
            np.concatenate(b["ksrc"]),
            np.concatenate(b["kdst"]),
            np.concatenate(b["kt"]),
            np.concatenate(b["ket"]),
        )
        multi_eq = bool(np.array_equal(sorted_keys(kk_k), sorted_keys(kk_v)))
        out[day] = DayAlign(
            src=src,
            dst=dst,
            t=t,
            et=et,
            s_k=s_k,
            s_v=s_v,
            mode="+".join(f"{m}:{c}" for m, c in sorted(b["modes"].items())),
            unmatched=int(b["um"]),
            n=int(len(src)),
            n_dup_frac_k=dup_row_frac(kk_k),
            n_dup_frac_v=dup_row_frac(kk_v),
            multi_eq=multi_eq,
        )
    _ALIGN[key] = out
    return out


def align_day(seed: int, split: str, day: str) -> DayAlign:
    by = align_split(seed, split)
    if day not in by:
        raise RuntimeError(f"no rows seed{seed} {split} {day}")
    return by[day]


def attach_to_v8(es: EventStream, day: DayAlign) -> EventStream:
    """Replace es.s with Kairos loss. Raw-day keys must be a super-multiset of stream keys
    in the same lexsort; skip extras (shelved). Unmatched stream rows must be 0.
    """
    orig = np.arange(day.n, dtype=np.int64)
    order = np.lexsort((orig, day.et, day.dst, day.src, day.t))
    rsrc, rdst, rt, ret, rsk = (
        day.src[order],
        day.dst[order],
        day.t[order],
        day.et[order],
        day.s_k[order],
    )
    s_new = np.empty(es.n, dtype=np.float64)
    j = 0
    n_raw = day.n
    unmatched = 0
    for i in range(es.n):
        sk = (int(es.src[i]), int(es.dst[i]), int(es.t[i]), int(es.etype[i]))
        found = False
        while j < n_raw:
            rk = (int(rsrc[j]), int(rdst[j]), int(rt[j]), int(ret[j]))
            if rk == sk:
                s_new[i] = float(rsk[j])
                j += 1
                found = True
                break
            j += 1
        if not found:
            unmatched += 1
            s_new[i] = np.nan
    if unmatched:
        raise RuntimeError(f"stream attach unmatched={unmatched} n={es.n} {es.split} {es.day} seed{es.seed}")
    return EventStream(
        dataset=es.dataset,
        seed=es.seed,
        split=es.split,
        day=es.day,
        t=es.t,
        src=es.src,
        dst=es.dst,
        etype=es.etype,
        s=s_new,
        proc=es.proc,
        obj=es.obj,
        src_type=es.src_type,
        dst_type=es.dst_type,
        proc_type=es.proc_type,
        kind=es.kind,
        meta=dict(es.meta, scorer=get_scorer(), attach_unmatched=0),
    )


def stream_cache_path(seed: int, split: str, day: str):
    return spec().art / DATASET / f"seed{seed}" / "stream" / f"{split}_{day}.npz"


def save_stream_cache(es: EventStream) -> None:
    cache = assert_write_path(stream_cache_path(es.seed, es.split, es.day))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        cache,
        t=es.t,
        src=es.src,
        dst=es.dst,
        etype=es.etype,
        s=es.s,
        proc=es.proc,
        obj=es.obj,
        src_type=es.src_type,
        dst_type=es.dst_type,
        proc_type=es.proc_type,
        kind=np.asarray(es.kind, dtype=object),
    )


def load_kairos_stream(seed: int, split: str, day: str) -> EventStream:
    cache = stream_cache_path(seed, split, day)
    if cache.is_file():
        z = np.load(cache, allow_pickle=True)
        return EventStream(
            dataset=DATASET,
            seed=seed,
            split=split,
            day=day,
            t=z["t"],
            src=z["src"],
            dst=z["dst"],
            etype=z["etype"],
            s=z["s"],
            proc=z["proc"],
            obj=z["obj"],
            src_type=z["src_type"],
            dst_type=z["dst_type"],
            proc_type=z["proc_type"],
            kind=z["kind"],
            meta={"cached": True, "scorer": get_scorer()},
        )
    es = load_stream(DATASET, seed, split, day)
    al = align_day(seed, split, day)
    if al.unmatched:
        raise RuntimeError(f"align unmatched={al.unmatched} seed{seed} {split} {day}")
    out = attach_to_v8(es, al)
    save_stream_cache(out)
    return out


def all_days() -> list[tuple[str, str]]:
    return [("val", VAL_DATES[DATASET])] + [("test", d) for d in TEST_DATES[DATASET]]
