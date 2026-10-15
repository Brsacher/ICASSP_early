# Paper numbers and the lab run that produced them

All of these use VELOX epoch 11 unless the row names another detector. Protocol P1, rearm `reset`. CADETS selected pair `q99+type`. THEIA selected pair `q99+kind`.

| Lab run | What it wrote | Paper ids |
| --- | --- | --- |
| v9-3 | `TABLE1_reset.md`, `per_cell_reset.csv`, `figA_reset_CADETS_E3.json`, `timing_single.json`, `TABLE1_reset_q99_kind.md` | T1–T9, Fig. 3, A3, D8, D10, Q1-1, Q1-2, Q1-6–Q1-10, Q3-1–Q3-4, S1–S3, S5, R1 |
| v9-5 | `RESULTS_v9_5_kairos.md` | X2 |
| v9-6 | `DECOMP_v9_6.md`, `DECOMP_v9_6.json` | A1, A2, A4, D9, Q1-3–Q1-5, Q2-1–Q2-7, Q3-5–Q3-8 |
| v9-8 | `RESULTS_v9_8_orthrus.md` | X1 |
| v9-11 | `THEIA_diag.md`, `PERSIST_three_scorers.md` | S4, X3 |
| v8.1 export | `plots/m0_events.csv` (seed 1, `q99+type`) | F1-1–F1-4, Q1-9 |
| frozen GT | `results/groundtruth_*.json` | D2–D6 (with `|M|` recovered from `per_cell_reset.csv`) |

Fig. 1 in the paper is the v8.1 picture for seed 1. Under v9 reset and P1, that seed's D1 at b=0 is still event 9 at 528.956 s. Checked by `scripts/verify_numbers.py`.
