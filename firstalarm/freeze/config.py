# Source: ecpg/fa at the v8.1 frozen-input builders (stream, ground truth, lineage, and the import closure of selfcheck).
# Public import path: firstalarm.freeze
"""v8 constants and artifact paths."""

from __future__ import annotations

from pathlib import Path

DATASETS = ("CADETS_E3", "THEIA_E3")
SEEDS = (0, 1, 2, 3, 4)
EPOCH = 11
BUDGETS = (0, 1, 2, 5, 10, 20, 50)
PAIRS = (("none", "kind"), ("none", "type"), ("q99", "kind"), ("q99", "type"))
RULES = ("D1", "D2", "D3", "D4")
C1_LO = 0.5
C1_HI = 2.0
N_MIN_KIND = 100
WARMUP = 5
PRE_T0_NS = 60 * 10**9
EFF_INHERIT = 0.5
C5_DENSITY = 0.05
C5_CONTRIB = 0.10

from firstalarm.roots import art_root, data_root, release_root

REPO = release_root()
_ART = art_root()

ART_ROOT = _ART / "v8"
LOG_ROOT = REPO / "results"
SUMMARY_JSON = _ART / "velox_seeds" / "SUMMARY_data.json"
GT_ROOT = data_root() / "Ground_Truth" / "orthrus"
CONFIG_PY = None

DB_NAME = {"CADETS_E3": "cadets_e3", "THEIA_E3": "theia_e3"}
VAL_DATES = {"CADETS_E3": "2018-04-10", "THEIA_E3": "2018-04-09"}
TEST_DATES = {
    "CADETS_E3": ("2018-04-06", "2018-04-11", "2018-04-12", "2018-04-13"),
    "THEIA_E3": ("2018-04-10", "2018-04-12", "2018-04-13"),
}
CREATION_SRC = {"CADETS_E3": "db_fork", "THEIA_E3": "stream_clone"}

A0_PROCS = (211776, 228725)
A0_HINT = {"nginx": 211776, "vugefal": 228725}
A0_NAMES = ("nginx", "master", "vugefal")
A0_DAY = "2018-04-06"
A1_NAME = "Nginx_Backdoor_12"
B0_NAME = "Firefox_Backdoor_Drakon_In_Memory"
REPORT_TAG = "v8_2"
CDF_BUDGETS = (1, 2, 5, 10, 20)
A0_SEEDS = (0, 1, 3)
ALERT0411_SEEDS = (0, 2)


def pair_tag(cap: str, prior: str) -> str:
    return f"{cap}_{prior}"


def art_dir(dataset: str, seed: int | None = None) -> Path:
    p = ART_ROOT / dataset
    if seed is not None:
        p = p / f"seed{seed}"
    return p


def log_dir() -> Path:
    return LOG_ROOT
