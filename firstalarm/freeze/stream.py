# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Build daily event streams from epoch-11 edge-loss CSVs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from firstalarm.freeze import etypes
from firstalarm.freeze.config import ART_ROOT, EPOCH
from firstalarm.freeze.names import program_name
from firstalarm.freeze.paths import RunPaths, get_run_paths, indexid2msg_path, list_loss_csvs
from firstalarm.freeze.timeutil import ns_to_day_us


@dataclass
class EventStream:
    dataset: str
    seed: int
    split: str
    day: str
    t: np.ndarray
    src: np.ndarray
    dst: np.ndarray
    etype: np.ndarray
    s: np.ndarray
    proc: np.ndarray
    obj: np.ndarray
    src_type: np.ndarray
    dst_type: np.ndarray
    proc_type: np.ndarray
    kind: np.ndarray
    meta: dict

    @property
    def n(self) -> int:
        return int(self.t.shape[0])


def load_indexid2msg(rp: RunPaths) -> dict:
    import torch

    obj = torch.load(indexid2msg_path(rp), map_location="cpu")
    out = {}
    for k, v in obj.items():
        out[int(k)] = v
    return out


def _node_type(nid: int, msg: dict) -> int:
    rec = msg.get(int(nid))
    if rec is None:
        return etypes.NTYPE["unknown"]
    name = rec[0] if isinstance(rec, (list, tuple)) else rec
    return etypes.NTYPE.get(str(name), etypes.NTYPE["unknown"])


def _node_label(nid: int, msg: dict) -> str:
    rec = msg.get(int(nid))
    if rec is None:
        return ""
    if isinstance(rec, (list, tuple)) and len(rec) >= 2:
        return str(rec[1])
    return str(rec)


def stream_npz_path(dataset: str, seed: int, split: str, day: str) -> Path:
    return ART_ROOT / dataset / f"seed{seed}" / "stream" / f"{split}_{day}.npz"


def build_streams(dataset: str, seed: int, split: str, rp: RunPaths | None = None) -> dict[str, EventStream]:
    etypes.assert_rel2id()
    rp = rp or get_run_paths(dataset, seed)
    msg = load_indexid2msg(rp)
    frames = []
    for fi, csv_path in enumerate(list_loss_csvs(rp, split, EPOCH)):
        df = pd.read_csv(
            csv_path,
            usecols=["loss", "srcnode", "dstnode", "time", "edge_type"],
            dtype={
                "loss": np.float64,
                "srcnode": np.int64,
                "dstnode": np.int64,
                "time": np.int64,
                "edge_type": np.int16,
            },
        )
        df["file_idx"] = np.int32(fi)
        df["row_idx"] = np.arange(len(df), dtype=np.int32)
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    t = all_df["time"].to_numpy(np.int64)
    days = ns_to_day_us(t)
    out = {}
    for day in sorted(set(days.tolist())):
        m = days == day
        idx = np.flatnonzero(m)
        sub = all_df.iloc[idx]
        t_d = sub["time"].to_numpy(np.int64)
        src = sub["srcnode"].to_numpy(np.int64)
        dst = sub["dstnode"].to_numpy(np.int64)
        et = sub["edge_type"].to_numpy(np.int16)
        s = sub["loss"].to_numpy(np.float64)
        orig = np.arange(len(sub), dtype=np.int64)
        order = np.lexsort((orig, et, dst, src, t_d))
        t_d, src, dst, et, s = t_d[order], src[order], dst[order], et[order], s[order]
        src_type = np.fromiter((_node_type(int(x), msg) for x in src), dtype=np.int8, count=len(src))
        dst_type = np.fromiter((_node_type(int(x), msg) for x in dst), dtype=np.int8, count=len(dst))
        emit_dst = np.isin(et, np.fromiter(etypes.EMIT_DST, dtype=np.int16))
        proc = np.where(emit_dst, dst, src)
        obj = np.where(emit_dst, src, dst)
        proc_type = np.where(emit_dst, dst_type, src_type)
        both_subj = (src_type == 0) & (dst_type == 0)
        no_proc = (src_type != 0) & (dst_type != 0)
        shelve = ((both_subj & (et != etypes.CLONE)) | no_proc | (proc_type != 0))
        keep = ~shelve
        meta = {
            "n_raw": int(len(t_d)),
            "n_keep": int(keep.sum()),
            "n_shelve_both_proc_non_clone": int((both_subj & (et != etypes.CLONE)).sum()),
            "n_shelve_no_proc": int(no_proc.sum()),
            "n_shelve_emit_not_proc": int(((~no_proc) & (proc_type != 0) & ~((both_subj & (et != etypes.CLONE)))).sum()),
            "n_unknown_type": int(((src_type == 3) | (dst_type == 3)).sum()),
        }
        t_d, src, dst, et, s = t_d[keep], src[keep], dst[keep], et[keep], s[keep]
        src_type, dst_type = src_type[keep], dst_type[keep]
        proc, obj, proc_type = proc[keep], obj[keep], proc_type[keep]
        kind = np.array([program_name(_node_label(int(p), msg)) for p in proc], dtype=object)
        es = EventStream(
            dataset=dataset, seed=seed, split=split, day=day,
            t=t_d, src=src, dst=dst, etype=et, s=s,
            proc=proc, obj=obj, src_type=src_type, dst_type=dst_type,
            proc_type=proc_type, kind=kind, meta=meta,
        )
        _save_stream(es)
        out[day] = es
    return out


def _save_stream(es: EventStream) -> Path:
    path = stream_npz_path(es.dataset, es.seed, es.split, es.day)
    path.parent.mkdir(parents=True, exist_ok=True)
    kind_i, vocab = _intern(es.kind)
    np.savez(
        path,
        t=es.t, src=es.src, dst=es.dst, etype=es.etype, s=es.s,
        proc=es.proc, obj=es.obj, src_type=es.src_type, dst_type=es.dst_type,
        proc_type=es.proc_type, kind_i=kind_i,
    )
    meta = dict(es.meta)
    meta["kind_vocab"] = vocab
    meta["dataset"] = es.dataset
    meta["seed"] = es.seed
    meta["split"] = es.split
    meta["day"] = es.day
    path.with_suffix(".meta.json").write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
    return path


def _intern(kind: np.ndarray) -> tuple[np.ndarray, list[str]]:
    vocab: list[str] = []
    idx = {}
    out = np.empty(len(kind), dtype=np.int32)
    for i, k in enumerate(kind):
        k = str(k)
        j = idx.get(k)
        if j is None:
            j = len(vocab)
            idx[k] = j
            vocab.append(k)
        out[i] = j
    return out, vocab


def load_stream(dataset: str, seed: int, split: str, day: str) -> EventStream:
    path = stream_npz_path(dataset, seed, split, day)
    z = np.load(path, allow_pickle=False)
    meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    vocab = meta["kind_vocab"]
    kind = np.array([vocab[int(i)] for i in z["kind_i"]], dtype=object)
    return EventStream(
        dataset=dataset, seed=seed, split=split, day=day,
        t=z["t"].astype(np.int64),
        src=z["src"].astype(np.int64),
        dst=z["dst"].astype(np.int64),
        etype=z["etype"].astype(np.int16),
        s=z["s"].astype(np.float64),
        proc=z["proc"].astype(np.int64),
        obj=z["obj"].astype(np.int64),
        src_type=z["src_type"].astype(np.int8),
        dst_type=z["dst_type"].astype(np.int8),
        proc_type=z["proc_type"].astype(np.int8),
        kind=kind,
        meta=meta,
    )


def stream_exists(dataset: str, seed: int, split: str, day: str) -> bool:
    return stream_npz_path(dataset, seed, split, day).is_file()
