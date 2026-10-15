"""Resolve Kairos / ORTHRUS / VELOX training dirs from SUMMARY_data.json (read-only)."""

from __future__ import annotations

from pathlib import Path

from firstalarm.kairos_config import DATASET, EPOCH, VELOX_SUMMARY, spec
from firstalarm.paths import RunPaths, list_loss_csvs, load_summary, remap


def load_scorer_summary(name: str | None = None) -> dict:
    return load_summary(spec(name).summary)


def load_kairos_summary() -> dict:
    return load_scorer_summary("kairos")


def load_velox_summary() -> dict:
    return load_summary(VELOX_SUMMARY)


def get_scorer_paths(seed: int, summary: dict | None = None, name: str | None = None) -> RunPaths:
    summary = summary if summary is not None else load_scorer_summary(name)
    label = (name or spec().name)
    for run in summary["runs"]:
        if run["dataset"] == DATASET and int(run["seed"]) == int(seed):
            p = run["paths"]
            return RunPaths(
                dataset=DATASET,
                seed=int(seed),
                training=remap(p["training"]),
                construction=remap(p["construction"]),
                evaluation=remap(p["evaluation"]),
            )
    raise KeyError(f"{label} run {DATASET} seed{seed}")


def get_kairos_paths(seed: int, summary: dict | None = None) -> RunPaths:
    return get_scorer_paths(seed, summary, name="kairos")


def get_velox_paths(seed: int, summary: dict | None = None) -> RunPaths:
    summary = summary if summary is not None else load_velox_summary()
    for run in summary["runs"]:
        if run["dataset"] == DATASET and int(run["seed"]) == int(seed):
            p = run["paths"]
            return RunPaths(
                dataset=DATASET,
                seed=int(seed),
                training=remap(p["training"]),
                construction=remap(p["construction"]),
                evaluation=remap(p["evaluation"]),
            )
    raise KeyError(f"velox run {DATASET} seed{seed}")


def loss_dir(rp: RunPaths, split: str) -> Path:
    return rp.training / "edge_losses" / split / f"model_epoch_{EPOCH}"


def csvs(rp: RunPaths, split: str) -> list[Path]:
    return list_loss_csvs(rp, split, EPOCH)
