"""Host/container unit test: scorer context does not point at VELOX/Kairos write roots."""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firstalarm.kairos_config import (
    KAIROS_ART,
    KAIROS_LOG,
    ORTHRUS_ART,
    ORTHRUS_LOG,
    get_scorer,
    set_scorer,
    spec,
)


def main() -> int:
    assert get_scorer() == "kairos"
    assert spec().art == KAIROS_ART
    assert spec().log == KAIROS_LOG
    set_scorer("orthrus")
    assert spec().name == "orthrus"
    assert spec().art == ORTHRUS_ART
    assert spec().log == ORTHRUS_LOG
    assert "v9_kairos" not in str(spec().art)
    assert "v9-5" not in str(spec().log)
    set_scorer("kairos")
    assert spec().art == KAIROS_ART
    print("scorer paths unit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
