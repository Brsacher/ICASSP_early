"""Repository root and data locations. No machine-specific paths."""

from __future__ import annotations

import os
from pathlib import Path

_PREFIXES = ("/home/pids/", "/home/cc/PIDSMaker/")


def release_root() -> Path:
    return Path(__file__).resolve().parents[1]


def art_root() -> Path:
    """Frozen streams, eval JSON, and PIDSMaker seed trees.

    Layout under FA_ART_ROOT: v8/, v9/, v9_kairos/, v9_orthrus/,
    velox_seeds/, kairos_seeds/, orthrus_seeds/.
    """
    env = os.environ.get("FA_ART_ROOT")
    if env:
        return Path(env)
    return release_root() / "artifacts"


def data_root() -> Path:
    """Ground-truth CSV and any local database inputs. Set FA_DATA_ROOT."""
    env = os.environ.get("FA_DATA_ROOT")
    if env:
        return Path(env)
    return release_root() / "data"


# Tops that live directly under FA_ART_ROOT (SUMMARY_data paths are relative to it).
_ART_TOP = (
    "v8/",
    "v9/",
    "v9_kairos/",
    "v9_orthrus/",
    "velox_seeds/",
    "kairos_seeds/",
    "orthrus_seeds/",
)


def remap_stored_path(p: str) -> Path:
    """Map a path recorded on the build machine onto FA_ART_ROOT / FA_DATA_ROOT."""
    s = str(p)
    for prefix in _PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if s.startswith("artifacts_ext/fa/"):
        return art_root() / s[len("artifacts_ext/fa/"):]
    if s.startswith("artifacts_ext/"):
        return art_root() / s[len("artifacts_ext/"):]
    if s.startswith("Ground_Truth/") or s.startswith("data/"):
        return data_root() / s
    if any(s.startswith(top) for top in _ART_TOP):
        return art_root() / s
    if s.startswith("/"):
        return Path(s)
    return release_root() / s
