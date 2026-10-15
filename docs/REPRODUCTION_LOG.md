# Reproduction log

Date: 2026-10-15 (container finished 09:41 UTC).

Image: `firstalarm-repro:latest`, id `sha256:7d12e7b9dba033beb2d65d5b4da747dfd47e1d456fd43071b76d826d144479ee` (`7d12e7b9dba0`). Base `python:3.9-slim`. No mount of the development tree, no Postgres, no GPU. Inputs from `data_staging` via `data/download.sh --from-dir /staging`. Command list: `r3_inner.sh`, which follows `docs/REPRODUCE.md`. Log: `r3_run.log`.

## Verify

Tier A, on the shipped `results/`:

```
measured 38463 / 54971 ev/s (paper: 38463 / 54971 on the original server)
all checks passed
```

Tier B, on the rebuilt `results/`:

```
measured 30431 / 45136 ev/s (paper: 38463 / 54971 on the original server)
all checks passed
```

The rate is printed and not judged. Event counts in `timing_single.json` are 1,987,981 (CADETS) and 5,002,043 (THEIA) on both runs.

## Wall clock and peak RSS

`/usr/bin/time -v`. RSS is `Maximum resident set size`.

| Step | Wall | RSS |
| --- | ---: | ---: |
| `run_fa_v9` (VELOX, all rearms) | 12:11.80 | 554,576 kB |
| `run_fa_v9_3 --phase tables` | 0:00.16 | 44,588 kB |
| `run_fa_v9_3 --phase timing` | 2:57.82 | 448,816 kB |
| `run_fa_v9_5` (KAIROS) | 8:48.70 | 397,004 kB |
| `run_fa_v9_8` (ORTHRUS) | 8:33.46 | 282,568 kB |
| `decomp_v9_6 --phase all` | 1:56.80 | 617,812 kB |
| `diag_v9_11 --phase all` | 1:58.59 | 510,380 kB |

Tier A `verify_numbers.py`, Fig. 3, and `download.sh` are not wrapped in `time`. The second verify is the last step and is not wrapped either.

## MD5

Byte-identical with the shipped `results/`:

- `DECOMP_v9_6.json`, `DECOMP_v9_6.md`
- `TABLE1_reset.md`, `TABLE1_reset.tex`, `TABLE1_reset_q99_kind.md`
- `THEIA_diag.md`
- `figA_reset_CADETS_E3.json`
- `per_cell_reset.csv`
- `groundtruth_CADETS_E3.json`, `groundtruth_THEIA_E3.json`
- `selection_CADETS_E3.json`, `selection_THEIA_E3.json`

`timing_single.json` matches on `n_events` and differs on `wall_s` / `events_per_s` (CADETS 65.33 s, 30431 ev/s; THEIA 110.82 s, 45136 ev/s).

Markdown that is not only a timestamp change:

- `PERSIST_three_scorers.md`: the shipped file has one extra sentence, `M_i 中无 k≥6 的键，故 6–10、>10 为空。` The generator does not emit it. The tables match.
- `RESULTS_v9_5_kairos.md` and `RESULTS_v9_8_orthrus.md`: precheck fields are `None` (no training-tree precheck in the public bundle), the fidelity section says the training tree is absent, and the replay wall-clock lines differ. The fixed ORTHRUS sentence and the KAIROS `d1_only: 2` line are present; verify checks them.

The rebuild also writes extra tables (below, fir, Kairos, ORTHRUS) and cache JSON. Those names are not in the shipped `results/`.

## Code changes made so this run could finish

- `scripts/run_fa_v9_3.py`: `--phase tables` copies `groundtruth_*.json` and `selection_*.json` into `results/`.
- `scripts/verify_numbers.py`: R1 checks the two event counts and prints the rate.
- `firstalarm/run.py`: skip the v8 `eval.json` regression when that file is not in the public streams.
- `firstalarm/kairos_report.py`: a missing `SUMMARY_data.json` does not abort the report; a missing precheck file is not treated as a failed precheck.
- `scripts/diag_v9_11.py`: gold comparison reads `configs/diag_gold/`, which is not deleted when `results/` is rebuilt.
- `Dockerfile`: `libc6-dev`, `time`, `zstd`; `FA_ART_ROOT` is not preset.
