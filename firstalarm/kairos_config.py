"""Scorer paths for Kairos / ORTHRUS. Does not change fa9.config ART_ROOT / LOG_ROOT (VELOX v9)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from firstalarm.config import REPO
from firstalarm.roots import art_root

_ART = art_root()
KAIROS_SUMMARY = _ART / "kairos_seeds" / "SUMMARY_data.json"
VELOX_SUMMARY = _ART / "velox_seeds" / "SUMMARY_data.json"
ORTHRUS_SUMMARY = _ART / "orthrus_seeds" / "SUMMARY_data.json"
KAIROS_ART = _ART / "v9_kairos"
ORTHRUS_ART = _ART / "v9_orthrus"
KAIROS_LOG = REPO / "results"
ORTHRUS_LOG = REPO / "results"
DATASET = "CADETS_E3"
SEEDS = (0, 1, 2, 3, 4)
EPOCH = 11
PREREG_COMMIT = "2913926546ea2c886d47667ad9df689515ad21db"


@dataclass(frozen=True)
class ScorerSpec:
    name: str
    summary: Path
    art: Path
    log: Path
    run_log: Path
    table1_tag: str
    cell_tag: str
    results_stem: str


SCORERS = {
    "kairos": ScorerSpec(
        name="kairos",
        summary=KAIROS_SUMMARY,
        art=KAIROS_ART,
        log=KAIROS_LOG,
        run_log=REPO / "results",
        table1_tag="kairos",
        cell_tag="kairos_reset",
        results_stem="RESULTS_v9_5_kairos",
    ),
    "orthrus": ScorerSpec(
        name="orthrus",
        summary=ORTHRUS_SUMMARY,
        art=ORTHRUS_ART,
        log=ORTHRUS_LOG,
        run_log=REPO / "results",
        table1_tag="orthrus",
        cell_tag="orthrus_reset",
        results_stem="RESULTS_v9_8_orthrus",
    ),
}

_current: ContextVar[str] = ContextVar("fa9_scorer", default="kairos")


def get_scorer() -> str:
    return _current.get()


def set_scorer(name: str) -> None:
    if name not in SCORERS:
        raise ValueError(f"unknown scorer {name}; want {sorted(SCORERS)}")
    _current.set(name)


def spec(name: str | None = None) -> ScorerSpec:
    return SCORERS[name or get_scorer()]


def assert_write_path(path: Path) -> Path:
    """Refuse writes into VELOX / Kairos / raw seed trees when scorer is orthrus."""
    s = str(path.resolve())
    if get_scorer() == "orthrus":
        art = str(art_root().resolve())
        allowed = (
            str((art_root() / "v9_orthrus").resolve()),
            str((REPO / "results").resolve()),
        )
        if not any(s == a or s.startswith(a + "/") for a in allowed):
            raise RuntimeError(f"orthrus write outside v9_orthrus or results: {path}")
        forbidden = (
            str((art_root() / "v8").resolve()),
            str((art_root() / "v9").resolve()),
            str((art_root() / "v9_kairos").resolve()),
            str((art_root() / "velox_seeds").resolve()),
            str((art_root() / "kairos_seeds").resolve()),
            str((art_root() / "orthrus_seeds").resolve()),
        )
        if any(s == f or s.startswith(f + "/") for f in forbidden):
            raise RuntimeError(f"orthrus must not write {path}")
    return path
