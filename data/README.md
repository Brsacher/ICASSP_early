# Frozen inputs

`download.sh` fetches five archives from the GitHub release `icassp2027-submission` (`https://github.com/Brsacher/ICASSP_early/releases/download/icassp2027-submission/`) and unpacks them into `$FA_ART_ROOT` (default `artifacts/` next to the repository). Checksums of the archives are `SHA256SUMS` in this directory.

The archives are derived from [DARPA Transparent Computing Engagement 3](https://github.com/darpa-i2o/Transparent-Computing), hosts CADETS and THEIA, scored by PIDSMaker at commit `84d9314bdd2cf6baad566cac12c222daf93e32b1`. They are released under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The raw DARPA traces are not in these archives and keep DARPA's own terms. ORTHRUS node lists used to build `groundtruth.json` ship with PIDSMaker under `Ground_Truth/orthrus/` and are not re-licensed here.

Code in this repository is Apache-2.0. See `NOTICE`.

## Where each archive unpacks

| Archive | Members |
| --- | --- |
| `velox_streams_cadets.tar.zst` | `v8/CADETS_E3/seed{0-4}/stream/` |
| `velox_streams_theia.tar.zst` | `v8/THEIA_E3/seed{0-4}/stream/` |
| `frozen_labels.tar.zst` | `v8/<HOST>/{groundtruth,lineage}.json`, `v9/<HOST>/selection.json` |
| `kairos_streams.tar.zst` | `v9_kairos/CADETS_E3/seed{0-4}/stream/*.npz` |
| `orthrus_streams.tar.zst` | `v9_orthrus/CADETS_E3/seed{0-4}/stream/*.npz` |

`<HOST>` is `CADETS_E3` or `THEIA_E3`. Extract with `tar --zstd -C "$FA_ART_ROOT"`.

## VELOX streams

25 files on CADETS (5 seeds × `val_2018-04-10` + test `2018-04-06`, `2018-04-11`, `2018-04-12`, `2018-04-13`) and 20 on THEIA (5 seeds × `val_2018-04-09` + test `2018-04-10`, `2018-04-12`, `2018-04-13`). Each day is an uncompressed NumPy `.npz` plus a sibling `.meta.json`. Built by `firstalarm.freeze.stream.build_streams` from PIDSMaker `edge_losses/{val,test}/model_epoch_11/*.csv` (epoch 11, the last saved epoch of a 12-epoch run).

Arrays, one row per kept event:

| Array | dtype | Unit |
| --- | --- | --- |
| `t` | int64 | nanoseconds, same clock as `t0`/`t1` in `groundtruth.json` |
| `src`, `dst` | int64 | PIDSMaker node `index_id` of the edge ends |
| `etype` | int16 | edge-type code: 1 CONNECT, 2 EXECUTE, 3 OPEN, 4 READ, 5 RECVFROM, 6 RECVMSG, 7 SENDMSG, 8 SENDTO, 9 WRITE, 10 CLONE |
| `s` | float64 | per-edge loss at epoch 11; a larger value is the more anomalous score |
| `proc` | int64 | acting process, the node the rule attributes the event to |
| `obj` | int64 | the other end of the edge |
| `src_type`, `dst_type`, `proc_type` | int8 | 0 subject, 1 file, 2 netflow, 3 unknown |
| `kind_i` | int32 | index into `kind_vocab` |

`.meta.json` fields: `dataset`, `seed`, `split` (`val` or `test`), `day` (`YYYY-MM-DD`), `kind_vocab` (program-name strings), `n_raw`, `n_keep`, and the shelve counters `n_shelve_no_proc`, `n_shelve_emit_not_proc`, `n_shelve_both_proc_non_clone`, `n_unknown_type`. Counts are events.

## KAIROS and ORTHRUS streams

CADETS only, the same 25 days as the VELOX CADETS streams. These are the caches `firstalarm.kairos_align.load_kairos_stream` reads (`v9_kairos` or `v9_orthrus`). They are not the `edge_losses` CSV files. Columns match the VELOX `.npz` except `kind` replaces `kind_i`: a NumPy object array of program-name strings, one per event. There is no `.meta.json`. `s` is that scorer's epoch-11 per-edge loss, aligned onto the VELOX event order.

## `groundtruth.json`

One file per host under `v8/<HOST>/`. Built by `firstalarm.freeze.groundtruth.build_groundtruth` from ORTHRUS node-level labels and PIDSMaker's attack windows.

| Field | Meaning |
| --- | --- |
| `dataset` | `CADETS_E3` or `THEIA_E3` |
| `gt_procs` | node ids of every attack subject, union of `P` |
| `window_0411` | CADETS only, `[t_start, t_end]` in nanoseconds for the 11 April window that is not an evaluated attack; `null` on THEIA |
| `extra.window_0411_text` | the same CADETS window as `US/Eastern` strings |
| `attacks[].name`, `day`, `idx` | attack id, calendar day, position in the PIDSMaker window list |
| `attacks[].t0`, `t1` | window start and end, nanoseconds |
| `attacks[].P` | subject (process) node ids |
| `attacks[].F` | file node ids |
| `attacks[].Nflow` | netflow node ids |
| `attacks[].G` | union of the labelled nodes |
| `attacks[].gt_file` | path of the ORTHRUS csv inside `Ground_Truth/orthrus/` |
| `attacks[].uuid_missing` | label uuids that were not in the database |

## `lineage.json`

One file per host under `v8/<HOST>/`. CADETS: `parent` maps a child subject node id to its parent, `t_c` maps the child to the fork time in nanoseconds, `n_rows` is the number of forks, `n_multi` and `n_parent_eq_child` count the rows the builder dropped. Keys in the JSON objects are decimal strings. THEIA's file has `n_rows: 0` and empty maps; process creation on that host is the `CLONE` edge inside the stream.

## `selection.json`

One file per host under `v9/<HOST>/`. Written by the VELOX replay from criterion C1 on the validation day. Fields: `cap` and `prior` (the chosen switch), `mark`, `c1_pass` (per-seed pass/fail), and `pairs` (for `none_kind`, `none_type`, `q99_kind`, `q99_type`: `n_pass` out of five seeds, plus the per-seed ratios). `n_pass` is a count of seeds. The shipped choice is `q99` + `type` on CADETS (4 of 5) and `q99` + `kind` on THEIA (5 of 5).
