# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""Resolve velox_seeds artifact paths from SUMMARY_data.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from firstalarm.freeze.config import EPOCH, REPO, SUMMARY_JSON


def remap(p: str) -> Path:
    from firstalarm.roots import remap_stored_path
    return remap_stored_path(p)


def listdir_sorted(path: Path | str) -> list[str]:
    files = os.listdir(path)
    files.sort(key=lambda f: int("".join(ch for ch in f if ch.isdigit()) or "0"))
    return files


@dataclass(frozen=True)
class RunPaths:
    dataset: str
    seed: int
    training: Path
    construction: Path
    evaluation: Path


def load_summary(path: Path | None = None) -> dict:
    with open(path or SUMMARY_JSON, encoding="utf-8") as f:
        return json.load(f)


def get_run_paths(dataset: str, seed: int, summary: dict | None = None) -> RunPaths:
    summary = summary if summary is not None else load_summary()
    for run in summary["runs"]:
        if run["dataset"] == dataset and int(run["seed"]) == int(seed):
            p = run["paths"]
            return RunPaths(
                dataset=dataset,
                seed=int(seed),
                training=remap(p["training"]),
                construction=remap(p["construction"]),
                evaluation=remap(p["evaluation"]),
            )
    raise KeyError(f"no run {dataset} seed{seed}")


def list_loss_csvs(rp: RunPaths, split: str, epoch: int = EPOCH) -> list[Path]:
    d = rp.training / "edge_losses" / split / f"model_epoch_{epoch}"
    return [d / name for name in listdir_sorted(d)]


def indexid2msg_path(rp: RunPaths) -> Path:
    return rp.construction / "indexid2msg" / "indexid2msg.pkl"


def result_pth_path(rp: RunPaths, epoch: int = EPOCH) -> Path:
    return rp.evaluation / "precision_recall_dir" / f"result_model_epoch_{epoch}.pth"
