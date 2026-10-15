"""Read PIDSMaker node-evaluation pickles. No machine paths."""

from __future__ import annotations

from pathlib import Path

TYPE_PAPER = {"subject": "process", "file": "file", "netflow": "socket"}


def _torch_load(path):
    import torch
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def load_indexid2msg(path: Path) -> dict[int, tuple[str, str]]:
    obj = _torch_load(path)
    out = {}
    for k, v in obj.items():
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            out[int(k)] = (str(v[0]), str(v[1]))
        else:
            out[int(k)] = (str(v), "")
    return out


def paper_type(raw: str) -> str:
    return TYPE_PAPER.get(raw, raw or "unknown")
