# Release manifest

Public tree assembled from the lab checkout. The lab tree itself is not modified.

Paper numbers and their status live in `docs/paper_numbers.md` (v2). `scripts/verify_numbers.py` checks the copies under `results/`.

## Layout

| path | role |
| --- | --- |
| `firstalarm/` | protocol P1 replay (`ecpg/fa9`, import name `firstalarm`) |
| `firstalarm/freeze/` | v8.1 builders for streams, ground truth, and lineage, plus the modules `selfcheck` and the Fig. 1 export import (`alerts`, `calibrate`, `rent`, `rules`, `evaluate`) |
| `scripts/` | `run_fa_v9.py`, `run_fa_v9_3.py`, `run_fa_v9_5.py`, `run_fa_v9_8.py`, `decomp_v9_6.py`, `diag_v9_11.py`, `precheck_kairos_v95.py`, the two unit tests, `verify_numbers.py` |
| `configs/` | budget grid, test days, switch choice, and the two `selection.json` copies |
| `results/` | tables, Fig. 3 JSON, decomposition, THEIA and persistence notes, Kairos and ORTHRUS result pages, frozen ground truth, selections |
| `plots/` | `make_fig3_v4.py`, `make_fig1_export.py`, `m0_events.csv` |
| `pidsmaker_patch/` | TGN eval-memory patch, not present in upstream HEAD |
| `docs/` | this file, `paper_numbers.md`, `PREREGISTRATION.md`, `RUN_LOG.md` |
| `data/` | download placeholder only |

Not included: `ecpg/fa` runners other than the freeze closure, `ecpg/d123`, `mem_reports`, exploratory scripts (`coverage_v9_10.py`, `decomp_v9_8.py`, `diag_kairos_v9_5d.py`, `probe_fork_clone.py`), `.npz` streams, `edge_losses`, and `.pth` weights.

## Paths

Recorded paths that begin with `/home/pids/` or `/home/cc/PIDSMaker/` are stripped and resolved under `FA_ART_ROOT` or `FA_DATA_ROOT` (`firstalarm/roots.py`). Those two prefixes remain only as strings to recognise old summary JSON. Nothing in this tree uses them as a directory to open.

`FA_DB_PASSWORD` is required before either `db.py` connects. There is no default password.

## Files whose path or secret handling changed relative to the lab copies

- `firstalarm/config.py`
- `firstalarm/freeze/config.py`
- `firstalarm/kairos_config.py`
- `firstalarm/paths.py`
- `firstalarm/freeze/paths.py`
- `firstalarm/db.py`
- `firstalarm/freeze/db.py`
- `firstalarm/roots.py` (new)
- `firstalarm/freeze/etypes.py` (PIDSMaker import moved inside `assert_rel2id`)
- `firstalarm/freeze/groundtruth.py` (PIDSMaker config import moved inside the builder)
- `firstalarm/kairos_report.py` (node-eval helpers, no lab script path)
- `firstalarm/node_eval.py` (new)
- `scripts/decomp_v9_6.py`
- `scripts/diag_v9_11.py`
- `scripts/precheck_kairos_v95.py` (no `git diff` against the lab protocol)
- `plots/make_fig1_export.py`
- `plots/make_fig3_v4.py` (usage path only)

`ecpg/d123/db.py` is not shipped, so it was not edited.
