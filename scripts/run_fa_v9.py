import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""RULES entry: python -m scripts.run_fa_v9 ..."""

from firstalarm.run import main

if __name__ == "__main__":
    raise SystemExit(main())
