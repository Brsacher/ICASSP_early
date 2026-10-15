"""CLI: python -m scripts.run_fa_v9 ..."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from firstalarm.config import (
    ART_ROOT,
    DATASETS,
    LOG_ROOT,
    SEEDS,
    V8_ART,
    pair_tag,
    variant_tag,
)
from firstalarm.pipeline import (
    choose_from_vals,
    load_eval,
    regress_cadets_below,
    regress_theia_below,
    test_seed,
    val_seed,
)
from firstalarm.table1 import (
    collect_evals,
    d1_cells,
    d1_mismatch,
    earliness_from_csv,
    earliness_of,
    write_fig_a,
    write_per_cell,
    write_table1,
)
from firstalarm.diag import write_standing


def _append_runlog(text: str) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    p = LOG_ROOT / "RUN_LOG.md"
    with p.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _parallel(fn, items, workers: int):
    if workers <= 1 or len(items) <= 1:
        return [fn(it) for it in items]
    out = [None] * len(items)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in as_completed(futs):
            i = futs[fut]
            out[i] = fut.result()
    return out


def _job_val(it):
    dataset, seed = it
    return val_seed(dataset, seed)


def _job_test(it):
    dataset, seed, cap, prior, rearm = it
    return test_seed(dataset, seed, cap, prior, rearm)


def _write_timing(jobs_meta: list[dict]) -> Path:
    ART_ROOT.mkdir(parents=True, exist_ok=True)
    path = ART_ROOT / "timing.json"
    path.write_text(json.dumps(jobs_meta, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorer", default="velox", choices=["velox", "kairos"])
    ap.add_argument("--rearm", default="below,reset,fir")
    ap.add_argument("--pair", default="selected,q99_kind")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--datasets", default="CADETS_E3,THEIA_E3")
    ap.add_argument("--phase", default="all", choices=["val", "test", "regress", "tables", "all"])
    args = ap.parse_args(argv)

    if args.scorer == "kairos":
        from firstalarm.kairos_run import main as kairos_main

        return kairos_main(argv)
    if args.seeds == "0-4":
        seeds = list(SEEDS)
    else:
        seeds = [int(x) for x in args.seeds.split(",")]
    datasets = [x.strip() for x in args.datasets.split(",") if x.strip()]
    rearms = [x.strip() for x in args.rearm.split(",") if x.strip()]
    pairs = [x.strip() for x in args.pair.split(",") if x.strip()]

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    ART_ROOT.mkdir(parents=True, exist_ok=True)
    git = "unknown"
    try:
        import subprocess
        git = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=os.getcwd(), text=True).strip()
    except Exception:
        pass
    _append_runlog(
        f"\n# start phase={args.phase} scorer={args.scorer} rearm={rearms} pair={pairs} "
        f"workers={args.workers} seeds={seeds} cwd={os.getcwd()} pid={os.getpid()} git={git}\n"
    )

    if args.phase in ("val", "all"):
        t0 = time.time()
        items = [(ds, s) for ds in datasets for s in seeds]
        _parallel(_job_val, items, args.workers)
        sels = {ds: choose_from_vals(ds, seeds) for ds in datasets}
        _append_runlog(f"## val {time.time()-t0:.1f}s sel={ {d: (v['cap'], v['prior'], v['mark']) for d,v in sels.items()} }\n")
    else:
        sels = {}
        for ds in datasets:
            p = ART_ROOT / ds / "selection.json"
            sels[ds] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"cap": "q99", "prior": "type", "mark": "missing"}

    def pair_list():
        out = []
        for ds in datasets:
            sel = (sels[ds]["cap"], sels[ds]["prior"])
            for pr in pairs:
                if pr == "selected":
                    out.append((ds, sel[0], sel[1], True))
                elif pr == "q99_kind":
                    out.append((ds, "q99", "kind", False))
                else:
                    cap, prior = pr.split("_", 1) if "_" in pr else ("q99", pr)
                    out.append((ds, cap, prior, False))
        # unique
        seen = set()
        uniq = []
        for row in out:
            key = (row[0], row[1], row[2])
            if key not in seen:
                seen.add(key)
                uniq.append(row)
        return uniq

    variants = []
    for ds, cap, prior, is_sel in pair_list():
        for rearm in rearms:
            if rearm != "reset" and not is_sel and ("q99_kind" in pairs and (cap, prior) == ("q99", "kind")):
                # only reset is required for the second pair
                if "selected" in pairs and (sels[ds]["cap"], sels[ds]["prior"]) != ("q99", "kind"):
                    continue
            variants.append((ds, cap, prior, rearm, is_sel))

    # required four: below/reset/fir selected + reset q99_kind
    if args.phase == "all":
        variants = []
        for ds in datasets:
            sc, sp = sels[ds]["cap"], sels[ds]["prior"]
            for rearm in ("below", "reset", "fir"):
                variants.append((ds, sc, sp, rearm, True))
            variants.append((ds, "q99", "kind", "reset", False))

    if args.phase in ("test", "all"):
        # CADETS below selected first for regression gate
        if args.phase == "all" and "CADETS_E3" in datasets and "below" in {v[3] for v in variants}:
            cad = [v for v in variants if v[0] == "CADETS_E3" and v[3] == "below" and v[4]]
            items = [(ds, s, cap, prior, rearm) for ds, cap, prior, rearm, _ in cad for s in seeds]
            t0 = time.time()
            _parallel(_job_test, items, args.workers)
            _append_runlog(f"## test CADETS below {time.time()-t0:.1f}s\n")
            v8_gate = V8_ART / "CADETS_E3" / "seed0" / "eval" / "eval.json"
            if not v8_gate.is_file():
                print(f"skip CADETS below regression; missing {v8_gate}")
                _append_runlog("## regress CADETS skipped (v8 eval.json is not in the public streams)\n")
            else:
                reg = regress_cadets_below(seeds, cad[0][1], cad[0][2])
                (LOG_ROOT / "REGRESS_CADETS_below.json").write_text(json.dumps(reg, indent=2, default=str), encoding="utf-8")
                _append_runlog(f"## regress CADETS pass={reg['pass']} window {reg['ok_window']}/{reg['n_window']} diffs={reg['n_diffs']}\n")
                if not reg["pass"]:
                    print("CADETS below regression FAILED; stop.")
                    print(json.dumps({"n_diffs": reg["n_diffs"], "sample": reg["diffs"][:12]}, default=str, indent=2))
                    return 4
            rest = [v for v in variants if not (v[0] == "CADETS_E3" and v[3] == "below" and v[4])]
        else:
            rest = variants
        items = [(ds, s, cap, prior, rearm) for ds, cap, prior, rearm, _ in rest for s in seeds]
        # unique jobs
        seen = set()
        uitems = []
        for it in items:
            if it not in seen:
                seen.add(it)
                uitems.append(it)
        t0 = time.time()
        _parallel(_job_test, uitems, args.workers)
        _append_runlog(f"## test rest n={len(uitems)} {time.time()-t0:.1f}s\n")

    if args.phase in ("regress", "all") and "CADETS_E3" in datasets:
        sc, sp = sels["CADETS_E3"]["cap"], sels["CADETS_E3"]["prior"]
        v8_gate = V8_ART / "CADETS_E3" / "seed0" / "eval" / "eval.json"
        if v8_gate.is_file() and (ART_ROOT / "CADETS_E3" / "seed0" / "eval" / f"eval_below_{pair_tag(sc, sp)}.json").is_file():
            reg = regress_cadets_below(seeds, sc, sp)
            (LOG_ROOT / "REGRESS_CADETS_below.json").write_text(json.dumps(reg, indent=2, default=str), encoding="utf-8")
            print(f"CADETS regress pass={reg['pass']} window {reg['ok_window']}/{reg['n_window']} diffs={reg['n_diffs']}")
            if args.phase == "regress" and not reg["pass"]:
                return 4

    if args.phase in ("tables", "all"):
        timing = []
        d1_by = {}
        table_specs = []
        for ds in datasets:
            sc, sp = sels[ds]["cap"], sels[ds]["prior"]
            table_specs.append(("below", "below", sc, sp))
            table_specs.append(("reset", "reset", sc, sp))
            table_specs.append(("fir", "fir", sc, sp))
            table_specs.append(("reset_q99_kind", "reset", "q99", "kind"))
        # unique tags
        done = set()
        for tag, rearm, cap, prior in table_specs:
            if tag in done:
                continue
            done.add(tag)
            cap_by = {}
            for ds in datasets:
                if tag == "reset_q99_kind":
                    cap_by[ds] = ("q99", "kind")
                else:
                    cap_by[ds] = (sels[ds]["cap"], sels[ds]["prior"])
            by = collect_evals(rearm, cap_by, seeds, datasets=datasets)
            write_table1(tag, by)
            write_fig_a(tag, by)
            csvp = write_per_cell(tag, by)
            write_standing(tag, rearm, cap_by, datasets, seeds)
            d1_by[tag] = d1_cells(by)
            for ds, evals in by.items():
                for ev in evals:
                    t = ev.get("timing") or {}
                    timing.append({
                        "dataset": ds, "seed": ev["seed"], "variant": tag,
                        "rearm": rearm, "cap": ev["cap"], "prior": ev["prior"],
                        "wall_s": t.get("wall_s"), "n_events": t.get("n_events"),
                        "events_per_s": t.get("events_per_s"),
                    })
            # self-check earliness
            for ds, evals in by.items():
                e2, _, _ = earliness_of(evals, 2, "D4")
                c2 = earliness_from_csv(csvp, ds, 2, "D4")
                if abs(e2 - c2) > 1e-12:
                    raise RuntimeError(f"earliness mismatch {tag} {ds} b=2 {e2} vs csv {c2}")
        _write_timing(timing)
        tags = list(d1_by)
        if tags:
            ref = d1_by[tags[0]]
            mism = []
            for t in tags[1:]:
                mism.extend({"vs": t, **row} for row in d1_mismatch(ref, d1_by[t]))
            (LOG_ROOT / "D1_COLUMN_CHECK.json").write_text(
                json.dumps({"ref": tags[0], "n_mismatch": len(mism), "mismatches": mism}, indent=2, default=str),
                encoding="utf-8",
            )
            if mism:
                raise RuntimeError(f"D1 columns differ across tables: {len(mism)} cells")
        if "THEIA_E3" in datasets and (V8_ART / "THEIA_E3" / "seed0" / "eval" / "eval.json").is_file():
            sc, sp = sels["THEIA_E3"]["cap"], sels["THEIA_E3"]["prior"]
            th = regress_theia_below(seeds, sc, sp)
            (LOG_ROOT / "REGRESS_THEIA_below.json").write_text(json.dumps(th, indent=2, default=str), encoding="utf-8")
            _append_runlog(f"## THEIA below diffs={th['n_diff']} same={th['n_same']}\n")
        _append_runlog("## tables done\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
