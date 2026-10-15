"""Load frozen v8 EventStream npz. Never write v8. Never rebuild."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from firstalarm.config import V8_ART


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


def stream_npz_path(dataset: str, seed: int, split: str, day: str) -> Path:
    return V8_ART / dataset / f"seed{seed}" / "stream" / f"{split}_{day}.npz"


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
