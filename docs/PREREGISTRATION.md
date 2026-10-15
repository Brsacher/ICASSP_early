# Pre-registration

This document states what was fixed before which run, with commit hashes and timestamps from the development repository, so that a reader can tell a pre-specified test from a development-set result. Times are EDT, as recorded by the run logs.

## Summary

- The ORTHRUS experiment is the only one that was pre-registered in the strict sense: its success criterion and its reporting sentences were committed before the ORTHRUS models were trained, and the paper reports the outcome in the fixed sentence.
- The KAIROS criterion is the same inequality, but it was first written down after the KAIROS replay had finished. The submitted paper's phrase "under a criterion fixed beforehand" is therefore accurate for ORTHRUS and not for KAIROS; this is erratum E3 in `docs/paper_numbers.md`.

Commit hashes and timestamps come from the authors' private development repository; docs/PROTOCOL_v9.history.txt is an export of that history. No third-party timestamp (OSF, AsPredicted) was obtained.

## The criterion

For a scorer other than VELOX, with switch setting chosen by criterion C1 on the validation day:

> gain ⇔ E_FA(b = 5) − E_D1(b = 5) ≥ 0.1 and F_FA(b = 5) ≤ F_D1(b = 20).

Three outcomes were pre-specified for ORTHRUS, each with a sentence to be used verbatim in the paper: (1) gain; (2) no gain, with signal (the event-level rule detects at least 3 of the 15 pairs at b = 5); (3) no gain, without signal.

The `run_logs/` paths in the timeline are files in the development repository. This release does not include them; `docs/RUN_LOG.md` is the mapping that is in the tree.

## Timeline

| Event | Commit / log | Time | 发布树里的对照 |
| --- | --- | --- | --- |
| Final protocol P1, rule ladder, budget grid, criterion C1 and reporting format (`PROTOCOL_v9.md`) | `c0020c44` (tag `v9-3`) | 2026-09-18 | `docs/PROTOCOL_v9.md`, `docs/PROTOCOL_v9.history.txt` |
| Main replay with VELOX's scores (Table 1, Fig. 3) | `run_logs/fa/v9/RUN_LOG.md` | 2026-09-18 to 09-19 | `docs/RUN_LOG.md` |
| KAIROS replay (v9-5) | `run_logs/v9-5/RUN_LOG.md` | 2026-09-20 03:43:30 – 03:47:57 | `docs/RUN_LOG.md` |
| KAIROS criterion first written (in `kairos_report.py`) | `54d37001` | 2026-09-20 03:50:37 | `docs/kairos_report.criterion.log.txt` |
| ORTHRUS section added to `PROTOCOL_v9.md`: criterion, three outcome sentences, "not to be changed hereafter"; the KAIROS criterion appears in the same commit as "same as for Kairos" | `29139265` | 2026-09-20 05:02:38 | `docs/PROTOCOL_v9.history.txt` |
| ORTHRUS training started (seed 0) | `run_logs/orthrus_seeds/RUN_LOG.md` | 2026-09-20 05:09:57 | `docs/RUN_LOG.md` |
| ORTHRUS replay (v9-8); `git diff 2913926 -- PROTOCOL_v9.md` empty at start | `run_logs/v9-8/pipeline.stdout` | 2026-09-20 08:29:19 | `docs/RUN_LOG.md` |

`git log -S 'Kairos'` and `git log -S '0.1'` on `PROTOCOL_v9.md` return only `29139265`; before 05:02:38 on 2026-09-20 the protocol file contained neither the word Kairos nor the inequality.

## Outcomes

| Scorer | Criterion fixed | E_FA(5) | E_D1(5) | ΔE | F_FA(5) | F_D1(20) | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VELOX (CADETS) | not applicable (development scorer; values for reference) | 0.728 | 0.483 | +0.245 | 12.0 | 15.0 | would count as gain |
| KAIROS (CADETS) | after the run | 0.000 | 0.090 | −0.090 | 20.75 | 145.25 | no gain; event-level rule detects 2 of 15 pairs |
| ORTHRUS (CADETS) | before training and replay | 0.082 | 0.168 | −0.086 | 23.25 | 41.50 | no gain, with signal; event-level rule detects 5 of 15 pairs, FirstAlarm 3 |

Pre-specified sentences:

- ORTHRUS, outcome (2), used in the paper: *"With ORTHRUS's per-event scores, which separate the attacks (the event-level rule detects 5 of the 15 pairs at b = 5), FirstAlarm adds no gain (0.08 against 0.17), so the gain is shown only with VELOX's scores."*
- KAIROS, written after the run: *"With Kairos's scores, for which [VELOX] reports a node-level ADP of 0.01 on this host, the event-level rule detects 2 of the 15 pairs and FirstAlarm none."*

The submitted paper compresses both into "showed no gain" for space; the numbers above are the ones that sentence stands for. "Event-level rule on X's scores" means rule D1 applied to X's per-edge losses with the protocol's calibration; it is not X's own alert procedure (ORTHRUS adds a K-Means step and KAIROS a time-window queue after thresholding; neither was run).

PROTOCOL_v9.md §5a pre-specified Table 1 with rows for b ∈ {2, 5}, quiet/spike blocks and † marks; the paper prints the b = 5 rows with ‡ marks for space. The full pre-specified table is results/TABLE1_reset.md.

## What this repository lets a reader check

- `docs/RUN_LOG.md` maps each paper number to the internal run (v9-3, v9-5, v9-6, v9-8, v9-11) and its log.
- `results/` holds the outputs of those runs unchanged.
- Tier B of `docs/REPRODUCE.md` regenerates them from the frozen scored streams.
