"""v9 constants and artifact paths."""

from __future__ import annotations

from pathlib import Path

DATASETS = ("CADETS_E3", "THEIA_E3")
SEEDS = (0, 1, 2, 3, 4)
EPOCH = 11
BUDGETS = (0, 1, 2, 5, 10, 20, 50)
TABLE_BUDGETS = (2, 5)
PAIRS = (("none", "kind"), ("none", "type"), ("q99", "kind"), ("q99", "type"))
RULES = ("D1", "D2", "D3", "D4")
REARMS = ("below", "reset", "fir")
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

V8_ART = _ART / "v8"
ART_ROOT = _ART / "v9"
LOG_ROOT = REPO / "results"
SPEC_PATH = REPO / "docs" / "PREREGISTRATION.md"
SUMMARY_JSON = _ART / "velox_seeds" / "SUMMARY_data.json"
KAIROS_SUMMARY = _ART / "kairos_seeds" / "SUMMARY_data.json"
GT_ROOT = data_root() / "Ground_Truth" / "orthrus"
CONFIG_PY = None  # resolved from the installed pidsmaker package when rebuilding GT

DB_NAME = {"CADETS_E3": "cadets_e3", "THEIA_E3": "theia_e3"}
VAL_DATES = {"CADETS_E3": "2018-04-10", "THEIA_E3": "2018-04-09"}
TEST_DATES = {
    "CADETS_E3": ("2018-04-06", "2018-04-11", "2018-04-12", "2018-04-13"),
    "THEIA_E3": ("2018-04-10", "2018-04-12", "2018-04-13"),
}
ATTACK_DATES = {
    "CADETS_E3": ("2018-04-06", "2018-04-12", "2018-04-13"),
    "THEIA_E3": ("2018-04-10", "2018-04-12"),
}
CREATION_SRC = {"CADETS_E3": "db_fork", "THEIA_E3": "stream_clone"}
WATCH_PROG = {"CADETS_E3": "nginx", "THEIA_E3": "firefox"}

PAPER_GROUP = {
    "Nginx_Backdoor_06": "quiet",
    "Nginx_Backdoor_12": "quiet",
    "Nginx_Backdoor_13": "spike",
    "Firefox_Backdoor_Drakon_In_Memory": "quiet",
    "Browser_Extension_Drakon_Dropper": "spike",
}

REPORT_TAG = "v9"


def pair_tag(cap: str, prior: str) -> str:
    return f"{cap}_{prior}"


def variant_tag(rearm: str, cap: str, prior: str, selected_cap: str, selected_prior: str) -> str:
    if (cap, prior) == (selected_cap, selected_prior):
        return rearm
    return f"{rearm}_{pair_tag(cap, prior)}"


def art_dir(dataset: str, seed: int | None = None) -> Path:
    p = ART_ROOT / dataset
    if seed is not None:
        p = p / f"seed{seed}"
    return p
