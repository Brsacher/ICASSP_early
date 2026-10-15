# Reproducing the paper

Three tiers. Each tier ends with `scripts/verify_numbers.py`, which asserts every entry of `docs/paper_numbers.md` against the files in `results/` with a tolerance of 1e-3.

| Tier | Starts from | Produces | Time | Needs |
| --- | --- | --- | --- | --- |
| A | `results/` as shipped | every number, Table 1, Fig. 3 | seconds | Python 3.9+ |
| B | frozen scored streams (GitHub release) | `results/` regenerated | about 40 min, under 1 GB RAM, one CPU | 392,654,968 bytes downloaded |
| C | raw DARPA TC E3 + PIDSMaker | the frozen streams | hours | GPU with 24 GB, Postgres |

Only Tier B reproduces the paper's cells exactly. Tier C re-trains the detectors, and training is not bit-reproducible across hardware. The Tier B timing is from `docs/REPRODUCTION_LOG.md`. Tier B also writes the `below` and `fir` variant tables, which the paper does not use, and `results/cache/` from the diagnosis.

## Conventions

- **Budgets** `b ∈ {0, 1, 2, 5, 10, 20, 50}`: the number of processes a rule flags on the benign validation day. `F` is the resulting number of flagged processes per test day that belong to no attack, averaged over test days and taken as the median over seeds.
- **Rules**: `D1` detector's own rule (event score against a threshold); `D2` memory within a process; `D3` memory with links across processes; `D4` = FirstAlarm (D3 beside D1 at its default threshold). Files use `D4`; the paper says FirstAlarm or "Ours".
- **Re-arm** `reset`: the sum restarts from zero after an alert (the paper). `below` and `fir` are variants kept for the sensitivity note.
- **Switch setting**: `q99_type` (cap on, per-type prior) is selected for CADETS, `q99_kind` (cap on, per-program prior) for THEIA, by criterion C1 on the validation day alone; `configs/selection_*.json` record the choice. The "both switches on" sensitivity row of the paper is `q99_kind` on CADETS.
- **Seeds**: PIDSMaker seeds 0–4 (featurization and training). `N = 15` attack–seed pairs on CADETS, `10` on THEIA.
- **Environment variables**: `FA_ART_ROOT` (default `./artifacts`) holds the frozen streams and the replay outputs; `FA_DATA_ROOT` (default `./data`) holds downloaded archives; `FA_DB_PASSWORD` is read only by the Tier C freeze step.

## Tier A — verify from the shipped results

```bash
pip install -r requirements.txt
python3 scripts/verify_numbers.py
python3 plots/make_fig3_v4.py results/figA_reset_CADETS_E3.json   # writes fig3_frontier_v4.pdf/.png
```

`verify_numbers.py` prints one `OK` line per entry (`T1 D1`, `Fig.3 b=5 D4`, `Q2-2`, …) and ends with `all checks passed`. Entries whose status in `docs/paper_numbers.md` is "论文有误 / paper erratum" are asserted against the repository's values, with the submitted wording quoted in a comment next to the assertion.

Table 1 is `results/TABLE1_reset.md` (CADETS columns from `eval_reset_q99_type.json`, THEIA from `eval_reset_q99_kind.json`); the per-cell values behind it are `results/per_cell_reset.csv`. Fig. 1's event table is `plots/m0_events.csv` (CADETS 6 April, seed 1).

## Tier B — replay from the frozen streams

### B.1 Fetch the inputs

```bash
bash data/download.sh            # five .tar.zst from the GitHub release icassp2027-submission
                                 # into $FA_DATA_ROOT, checked against data/SHA256SUMS,
                                 # then unpacked with tar --zstd -C $FA_ART_ROOT
bash data/download.sh --from-dir /path/to/archives
                                 # skip the download; sha256sum -c, then unpack
```

Members are rooted at `v8/`, `v9/`, `v9_kairos/` and `v9_orthrus/`, so one extract into `$FA_ART_ROOT` is the layout the code opens. After this step:

- `$FA_ART_ROOT/v8/CADETS_E3/` holds `groundtruth.json`, `lineage.json` and five `seed*/stream/` directories (`val_2018-04-10` plus test days `2018-04-06`, `-11`, `-12`, `-13`), each day a `.npz` and a `.meta.json`.
- `$FA_ART_ROOT/v8/THEIA_E3/` holds the same labels plus `val_2018-04-09` and test days `2018-04-10`, `-12`, `-13`.
- `$FA_ART_ROOT/v9/CADETS_E3/selection.json` and `$FA_ART_ROOT/v9/THEIA_E3/selection.json` are the frozen switch choices. The replay overwrites them.
- `$FA_ART_ROOT/v9_kairos/CADETS_E3/seed*/stream/*.npz` and `$FA_ART_ROOT/v9_orthrus/CADETS_E3/seed*/stream/*.npz` are the aligned caches (CADETS only, 25 files each).

### B.2 Replay VELOX's scores (Table 1, Fig. 3)

```bash
export FA_ART_ROOT=$PWD/artifacts FA_DATA_ROOT=$PWD/data
python3 -m scripts.run_fa_v9 --scorer velox --rearm reset --pair selected,q99_kind
```

This calibrates on the validation day, selects the switch setting by C1, replays all test days for the seven budgets, and writes `$FA_ART_ROOT/v9/<HOST>/seed*/eval/eval_reset_<cap>_<prior>.json` plus `selection.json`. One seed takes about 52 s on CADETS (1,987,981 test events) and 91 s on THEIA (5,002,043) in a single process, all budgets at once; `--workers` parallelises over seeds.

```bash
python3 -m scripts.run_fa_v9_3 --phase tables     # results/TABLE1_reset.{md,tex}, per_cell_reset.csv,
                                                  # figA_reset_CADETS_E3.json, TABLE1_reset_q99_kind.md,
                                                  # plus copies of groundtruth_*.json and selection_*.json
python3 -m scripts.run_fa_v9_3 --phase timing     # results/timing_single.json
                                                  # event counts are fixed; events/s depends on the machine
```

### B.3 Other scorers (Discussion)

```bash
python3 -m scripts.run_fa_v9_5 --scorer kairos --phase all   # results/RESULTS_v9_5_kairos.md
python3 -m scripts.run_fa_v9_8 --scorer orthrus --phase all  # results/RESULTS_v9_8_orthrus.md
```

Both read the aligned `.npz` caches from the `kairos_streams` / `orthrus_streams` archives (CADETS only). They calibrate on the validation day, write `seed*/calib/val.json`, `seed*/eval/eval_reset_*.json` and `selection.json` under `$FA_ART_ROOT/v9_kairos` or `v9_orthrus`, and print the pre-specified outcome sentence (`docs/PREREGISTRATION.md`). `--phase all` is the default. `run_fa_v9_5` defaults to `--scorer kairos`; `run_fa_v9_8` must be given `--scorer orthrus` because the shared parser defaults to `kairos`. The precheck and fidelity sections of `RESULTS_v9_5_kairos.md` and `RESULTS_v9_8_orthrus.md` need the Tier C training artifacts; Tier B reproduces the numbers in those reports.

### B.4 Decomposition and diagnosis (Q1–Q3, Scope)

```bash
python3 -m scripts.decomp_v9_6 --phase all        # results/DECOMP_v9_6.{md,json}
python3 -m scripts.diag_v9_11  --phase all        # results/PERSIST_three_scorers.md, THEIA_diag.md
```

`decomp_v9_6` reads the VELOX replay from B.2. `diag_v9_11 --phase all` reads the three CADETS stream trees and the `val.json` / `eval_reset_*.json` files written by B.2 and B.3. Phase B of the diagnosis reads the THEIA VELOX streams and the THEIA replay from B.2.

### B.5 Check

```bash
python3 scripts/verify_numbers.py
```

### Expected results

| Quantity | Value |
| --- | --- |
| CADETS, b = 5: pairs detected, D1 / D3 / FirstAlarm | 9 / 12 / 14 of 15 |
| CADETS, b = 5: E, D1 / D3 / FirstAlarm | 0.4828 / 0.5969 / 0.7280 |
| CADETS, b = 5: F, D1 / D3 / FirstAlarm | 5.0 / 12.0 / 12.0 |
| CADETS, b = 20, D1: pairs, E, F | 10, 0.5453, 15.0 |
| THEIA, b = 5: E, D1 / FirstAlarm | 0.4246 / 0.4252 |
| THEIA, b = 5: F, D1 / FirstAlarm | 10.67 / 20.0 |
| Ladder at b = 5 (CADETS): D1, D2, D3, FirstAlarm | 0.4828, 0.5874, 0.5969, 0.7280 |
| F' (alerts on malicious processes before t0 counted as false positives) | 12.5 |
| ORTHRUS scores, b = 5: E, D1 / FirstAlarm | 0.1682 / 0.0820 |
| KAIROS scores, b = 5: pairs, D1 / FirstAlarm | 2 / 0 of 15 |
| Replay throughput, single process | ~38k ev/s CADETS, ~55k ev/s THEIA |

Throughput depends on the machine; everything else should match to the printed precision.

## Tier C — re-train the detectors and rebuild the streams

1. **PIDSMaker.** Clone `https://github.com/ubc-provenance/PIDSMaker` at commit `84d9314bdd2cf6baad566cac12c222daf93e32b1` and follow its install guide: <https://ubc-provenance.github.io/PIDSMaker/ten-minute-install/> (same text in that commit at `docs/docs/ten-minute-install.md`). That image is Python 3.9 with PyTorch 1.13.1 and CUDA 11.7, plus Postgres for the parsed graphs. Load the CADETS_E3 and THEIA_E3 databases with its scripts. This repository's Dockerfile (`python:3.9-slim` plus `requirements.txt`) covers Tiers A and B only. For KAIROS and ORTHRUS, apply `pidsmaker_patch/2026-09-18_tgn_eval_oom.patch` first (`git apply`); it chunks the TGN memory update at validation time and changes no output.
2. **Train VELOX**, one process per seed. The ten resolved configs of the runs that produced the published streams, with absolute paths removed, are `configs/pidsmaker/velox_CADETS_E3_seed{0-4}.yml` and `configs/pidsmaker/velox_THEIA_E3_seed{0-4}.yml`. CADETS uses `node_hid_dim` and `node_out_dim` 256 with `lr` 0.0001; THEIA uses 320 and 0.001, with `featurization.emb_dim` 256 on both. That difference comes from PIDSMaker's tuned configuration for each host. Stock `config/velox.yml` includes `orthrus_non_snooped` and has `node_out_dim: 128`; it does not carry these sizes. The entry point is `python -m pidsmaker.main` (there is no `pidsmaker.py` and no `--seed`). The flags below are the values in those files:

   ```bash
   python -m pidsmaker.main velox CADETS_E3 \
     --featurization.seed=K --training.seed=K --featurization.emb_dim=256 \
     --training.num_epochs=12 --training.lr=0.0001 \
     --training.node_hid_dim=256 --training.node_out_dim=256 \
     --training.encoder.dropout=0.3 --training.encoder.used_methods=none
   python -m pidsmaker.main velox THEIA_E3 \
     --featurization.seed=K --training.seed=K --featurization.emb_dim=256 \
     --training.num_epochs=12 --training.lr=0.001 \
     --training.node_hid_dim=320 --training.node_out_dim=320 \
     --training.encoder.dropout=0.3 --training.encoder.used_methods=none
   ```

   `K` is 0, 1, 2, 3 or 4, and the two seed flags must match. The last saved epoch is `model_epoch_11`. Keep `edge_losses/{val,test}/model_epoch_11/*.csv` and `indexid2msg.pkl` under `$FA_ART_ROOT/velox_seeds/`. Then build the index the freeze step reads:

   ```bash
   export FA_ART_ROOT=$PWD/artifacts
   python3 scripts/summarize_velox_seeds.py    # writes $FA_ART_ROOT/velox_seeds/SUMMARY_data.json
   ```

   Paths in that JSON are relative to `FA_ART_ROOT`. `configs/pidsmaker/SUMMARY_data.example.json` is the same shape for the published runs (`runs[].paths.training`, `construction`, `evaluation`). `scripts/summarize_kairos_seeds.py` and `scripts/summarize_orthrus_seeds.py` do the same for `$FA_ART_ROOT/kairos_seeds` and `$FA_ART_ROOT/orthrus_seeds`.
3. **Freeze the inputs.** `firstalarm.freeze` has no combined CLI. With the Postgres databases reachable and `FA_DB_PASSWORD` set, call the three builders (they write under `$FA_ART_ROOT/v8/<HOST>/`):

   ```bash
   python3 -c 'from firstalarm.freeze.stream import build_streams; [build_streams(h, s, sp) for h in ("CADETS_E3", "THEIA_E3") for s in range(5) for sp in ("val", "test")]'
   python3 -c 'from firstalarm.freeze.lineage import build_lineage; from firstalarm.freeze.groundtruth import build_groundtruth; [build_groundtruth(h, build_lineage(h)) for h in ("CADETS_E3", "THEIA_E3")]'
   ```

   Streams are one `.npz` per day plus a `.meta.json`. CADETS lineage comes from `EVENT_FORK` in Postgres. THEIA's `lineage.json` stays empty; its creations are `CLONE` events inside the stream. `groundtruth.json` is built from ORTHRUS's node-level labels (`$FA_DATA_ROOT/Ground_Truth/orthrus/`) and PIDSMaker's attack windows.
4. **Optional self-check.** `--real` compares `D1` at `b = 0` with the processes VELOX itself flags. `--host` is `CADETS_E3` (the default) or `THEIA_E3`:

   ```bash
   python3 -m firstalarm.freeze.selfcheck --real --host CADETS_E3
   python3 -m firstalarm.freeze.selfcheck --real --host THEIA_E3
   ```

   On CADETS the two sets match on every seed. On THEIA they differ only on `CLONE` children (seed 3: seven, seed 4: one). `--real` also needs each run's `result.pth`.
5. **KAIROS and ORTHRUS.** Train with `python -m pidsmaker.main kairos CADETS_E3` and `python -m pidsmaker.main orthrus_non_snooped CADETS_E3`, same seed flags, five seeds. There is no `scripts/kairos_align`. Alignment runs inside `firstalarm.kairos_align.load_kairos_stream` when the cache `.npz` is absent, which the replay calls:

   ```bash
   python3 -m scripts.run_fa_v9_5 --scorer kairos --phase all
   python3 -m scripts.run_fa_v9_8 --scorer orthrus --phase all
   ```

   If `kairos_streams.tar.zst` / `orthrus_streams.tar.zst` are already unpacked, the replay reads those files and does not re-align. The pre-check (`python3 -m scripts.precheck_kairos_v95 --scorer kairos` or `--scorer orthrus`) asserts equal key multisets per day before a fresh alignment.
6. Continue at **B.2**.

What will differ: the learned models and therefore every score. VELOX's authors report seed-to-seed deviations of the detection score that often approach 100%. Expect the protocol's qualitative picture (FirstAlarm detects more pairs than D1 at b = 5 on CADETS; no gain on THEIA, ORTHRUS, KAIROS) but not the exact cells.

## Hardware used for the paper

One server: Intel Core i9-13900K, 128 GB RAM, two NVIDIA GeForce RTX 4090 (24 GB each), Debian 13. Detectors trained in PIDSMaker's Docker image (Python 3.9.25, PyTorch 1.13.1+cu117). The replay (Tiers A/B) uses no GPU.

## Where each paper number comes from

`docs/paper_numbers.md`: one row per number, with the source value, the script, the output file and line, and a status. Section 12 lists the errata found while building this repository.
