"""Summarise a KAIROS CADETS tree and write SUMMARY_data.json.

    FA_ART_ROOT=... python3 scripts/summarize_kairos_seeds.py

Reads $FA_ART_ROOT/kairos_seeds and writes
$FA_ART_ROOT/kairos_seeds/SUMMARY_data.json. Paths are relative to FA_ART_ROOT.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import OrderedDict

import pandas as pd
import torch
import yaml

import os
from pathlib import Path

def _art_root() -> str:
    env = os.environ.get("FA_ART_ROOT")
    if env:
        return env
    return str(Path(__file__).resolve().parents[1] / "artifacts")

REPO = _art_root()

def rel_art(p: str) -> str:
    """Path stored in SUMMARY_data.json, relative to FA_ART_ROOT."""
    if not p:
        return p
    ap = os.path.abspath(p)
    root = os.path.abspath(REPO) + os.sep
    if ap.startswith(root):
        return ap[len(root):]
    return p
EXT_ROOT = os.path.join(REPO, "kairos_seeds")
LOG_ROOT = EXT_ROOT
EPOCHS = [0, 1, 3, 5, 7, 9, 11]
SEED_TASKS = ["featurization", "feat_inference", "batching", "training", "evaluation"]
SHARED_TASKS = ["construction", "transformation"]
DATASET = "CADETS_E3"
GPU_DEFAULT = 0
EPOCH_LAST = 11


def plain(v):
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:  # noqa: BLE001
            return str(v)
    if isinstance(v, (int, float, str)) or v is None:
        return v
    return str(v)


def discover_runs():
    runs = []
    for yml in sorted(glob.glob(f"{EXT_ROOT}/evaluation/evaluation/*/run_config.yml")):
        cfg = yaml.safe_load(open(yml))
        if cfg.get("_model") != "kairos":
            continue
        ds = cfg["dataset"]["name"]
        if ds != DATASET:
            continue
        fseed, tseed = cfg["featurization"]["seed"], cfg["training"]["seed"]
        paths = {t: cfg[t]["_task_path"] for t in SHARED_TASKS + SEED_TASKS}
        attacks = [
            a[0].split("/")[-1].replace("node_", "").replace(".csv", "")
            for a in cfg["dataset"]["attack_to_time_window"]
        ]
        runs.append(
            dict(
                dataset=ds,
                seed=tseed,
                featurization_seed=fseed,
                training_seed=tseed,
                run_config=yml,
                paths=paths,
                attacks=attacks,
            )
        )
    return sorted(runs, key=lambda r: r["seed"])


def load_stats(eval_path):
    out = OrderedDict()
    pr = os.path.join(eval_path, "precision_recall_dir")
    for ep in EPOCHS:
        f = os.path.join(pr, f"stats_model_epoch_{ep}.pth")
        out[ep] = {k: plain(v) for k, v in torch.load(f).items()} if os.path.exists(f) else None
    return out


def val_stats(train_path, ep):
    d = os.path.join(train_path, "edge_losses", "val", f"model_epoch_{ep}")
    if not os.path.isdir(d):
        return None
    tot, n, mx = 0.0, 0, float("-inf")
    for name in sorted(os.listdir(d)):
        s = pd.read_csv(os.path.join(d, name), usecols=["loss"])["loss"]
        if len(s):
            tot += float(s.sum())
            n += len(s)
            mx = max(mx, float(s.max()))
    return dict(max=mx if n else None, mean=(tot / n) if n else None, n=n)


def parse_seed_log(path):
    txt = open(path, encoding="utf-8", errors="replace").read() if os.path.exists(path) else ""
    wall = re.search(r"Elapsed \(wall clock\) time \(seconds\): ([0-9.]+)", txt)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", txt)
    start = re.search(r"host start .* seed=(\d+) gpu=(\d+)", txt)
    host_start = re.search(r"\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [A-Z]+)\] host start", txt)
    host_end = re.search(r"\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [A-Z]+)\] host end", txt)
    rc = re.search(r"host end .* rc=(\d+)", txt)
    gpus = [float(x) for x in re.findall(r"Training finished - GPU memory: ([0-9.]+) GB", txt)]
    train_gpu_gb = max(gpus) if gpus else None
    finished = len(re.findall(r"Run finished", txt))
    return dict(
        start=host_start.group(1) if host_start else None,
        end=host_end.group(1) if host_end else None,
        wall_s=float(wall.group(1)) if wall else None,
        rss_kb=int(rss.group(1)) if rss else None,
        rss_gb=round(int(rss.group(1)) / 1024 / 1024, 2) if rss else None,
        rc=int(rc.group(1)) if rc else None,
        finished=finished,
        train_gpu_gb=train_gpu_gb,
        gpu=int(start.group(2)) if start else GPU_DEFAULT,
    )


def load_watch():
    p = os.path.join(LOG_ROOT, "WATCH.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    runs = discover_runs()
    watch = load_watch()
    seeds_watch = watch.get("seeds", {})
    data = {
        "runs": [],
        "completeness": {},
        "edge_diff": {},
        "baseline": {},
        "paper_compare": {},
        "val_rule": {},
        "coverage": {},
        "scorer": "kairos",
        "dataset": DATASET,
        "epoch_last": EPOCH_LAST,
    }
    done_files = sorted(glob.glob(f"{EXT_ROOT}/**/done.txt", recursive=True))
    missing = []
    found = {r["seed"] for r in runs}
    for k in range(5):
        if k not in found:
            missing += [(DATASET, k, t) for t in SEED_TASKS]
    for r in runs:
        for t in SHARED_TASKS + SEED_TASKS:
            if not os.path.exists(os.path.join(r["paths"][t], "done.txt")):
                missing.append((DATASET, r["seed"], t))
        r["stats"] = load_stats(r["paths"]["evaluation"])
        r["stats_missing"] = [ep for ep in EPOCHS if r["stats"][ep] is None]
        r["val"] = {ep: val_stats(r["paths"]["training"], ep) for ep in EPOCHS}
        valid = [ep for ep in EPOCHS if r["val"][ep] and r["val"][ep]["mean"] is not None]
        r["val_rule_epoch"] = min(valid, key=lambda e: r["val"][e]["mean"]) if valid else None
        r["best_epoch"] = None
        best_adp, best_disc = float("-inf"), float("-inf")
        for ep in EPOCHS:
            s = r["stats"].get(ep)
            if not s:
                continue
            if (s["adp_score"] > best_adp) or (s["adp_score"] == best_adp and s["discrimination"] > best_disc):
                r["best_epoch"] = ep
                best_adp, best_disc = s["adp_score"], s["discrimination"]
        slog = parse_seed_log(os.path.join(LOG_ROOT, f"seed{r['seed']}.log"))
        wseed = seeds_watch.get(str(r["seed"]), {})
        peak_mib = wseed.get("peak_mem_mib")
        if peak_mib is None and slog["train_gpu_gb"] is not None:
            peak_mib = int(round(slog["train_gpu_gb"] * 1024))
        val_peak = wseed.get("val_peak_mem_mib")
        r["epoch_last"] = EPOCH_LAST
        r["wall_s"] = slog["wall_s"]
        r["gpu"] = slog["gpu"] if slog["gpu"] is not None else GPU_DEFAULT
        r["peak_mem_mib"] = peak_mib
        r["train_gpu_gb"] = slog["train_gpu_gb"]
        r["val_peak_mem_mib"] = val_peak
        r["run_log"] = dict(
            start=slog["start"],
            end=slog["end"],
            dur_s=str(int(slog["wall_s"])) if slog["wall_s"] is not None else None,
            rc=str(slog["rc"]) if slog["rc"] is not None else None,
            rss_kb=str(slog["rss_kb"]) if slog["rss_kb"] is not None else None,
            rss_gb=str(slog["rss_gb"]) if slog["rss_gb"] is not None else None,
            done="7/7" if not any(x[1] == r["seed"] for x in missing) else "incomplete",
            finished=str(slog["finished"]),
        )
        r["coverage"] = {}

    data["completeness"] = dict(
        done_count=len(done_files),
        expected=7 + 5 * 5,  # 2 shared + 5 seeds × 5 seed-tasks（construction/transform 共享）
        missing=missing,
        du=os.popen(f"du -sh '{EXT_ROOT}' 2>/dev/null | cut -f1").read().strip(),
    )
    data["runs"] = [
        dict(
            dataset=r["dataset"],
            seed=r["seed"],
            featurization_seed=r["featurization_seed"],
            training_seed=r["training_seed"],
            run_config=rel_art(r["run_config"]),
            paths={k: rel_art(v) for k, v in r["paths"].items()},
            attacks=r["attacks"],
            best_epoch=r["best_epoch"],
            val_rule_epoch=r["val_rule_epoch"],
            stats_missing=r["stats_missing"],
            val={str(k): v for k, v in r["val"].items()},
            run_log=r["run_log"],
            coverage=r["coverage"],
            stats={str(ep): s for ep, s in r["stats"].items()},
            epoch_last=r["epoch_last"],
            wall_s=r["wall_s"],
            gpu=r["gpu"],
            peak_mem_mib=r["peak_mem_mib"],
            train_gpu_gb=r["train_gpu_gb"],
            val_peak_mem_mib=r["val_peak_mem_mib"],
        )
        for r in runs
    ]
    out = os.path.join(LOG_ROOT, "SUMMARY_data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)
    print(f"wrote {out} runs={len(data['runs'])} missing={len(missing)}")
    return 0 if not missing else 2


if __name__ == "__main__":
    sys.exit(main())
