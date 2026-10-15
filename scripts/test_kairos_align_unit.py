"""No-data unit test for Kairos window alignment (host or container)."""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from firstalarm.kairos_align import align_window, dup_row_frac, pack_keys


def _df(rows):
    return pd.DataFrame(rows, columns=["loss", "srcnode", "dstnode", "time", "edge_type"])


def main() -> int:
    pos = _df([[0.1, 1, 2, 10, 3], [0.2, 1, 2, 11, 3], [0.3, 4, 5, 12, 1]])
    vel = _df([[9.0, 1, 2, 10, 3], [8.0, 1, 2, 11, 3], [7.0, 4, 5, 12, 1]])
    s, um, mode = align_window(pos, vel)
    assert mode == "position" and um == 0
    assert np.allclose(s, [0.1, 0.2, 0.3])

    k = _df([[0.5, 1, 2, 10, 3], [0.6, 1, 2, 10, 3], [0.7, 9, 9, 1, 1]])
    v = _df([[1.0, 9, 9, 1, 1], [2.0, 1, 2, 10, 3], [3.0, 1, 2, 10, 3]])
    s, um, mode = align_window(k, v)
    assert mode == "key_occ" and um == 0
    assert np.allclose(s, [0.7, 0.5, 0.6])

    keys = pack_keys([1, 1, 2], [2, 2, 3], [10, 10, 11], [3, 3, 1])
    assert abs(dup_row_frac(keys) - 2 / 3) < 1e-12
    print("align_window unit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
