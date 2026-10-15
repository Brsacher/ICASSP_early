import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""v9-8: python -m scripts.run_fa_v9_8 --scorer orthrus --phase all --workers 2"""

from firstalarm.kairos_run import main

if __name__ == "__main__":
    raise SystemExit(main())
