"""Kairos / ORTHRUS scorer CLI. Does not write fa/v8 or fa/v9 (VELOX)."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from firstalarm.kairos_config import DATASET, SEEDS, assert_write_path, set_scorer, spec
from firstalarm.kairos_pipeline import choose_from_vals, test_seed, val_seed
from firstalarm.kairos_report import (
    collect,
    scale_table,
    write_evidence,
    write_fig_a,
    write_per_cell,
    write_results,
    write_standing,
    write_table1,
)


def _append_runlog(text: str) -> None:
    sp = spec()
    log_dir = assert_write_path(sp.run_log)
    report_dir = assert_write_path(sp.log)
    log_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    for p in (log_dir / "RUN_LOG.md", report_dir / "RUN_LOG.md"):
        with p.open("a", encoding="utf-8") as f:
            f.write(text if text.endswith("\n") else text + "\n")


def _parallel(fn, items, workers: int):
    if workers <= 1 or len(items) <= 1:
        return [fn(it) for it in items]
    out = [None] * len(items)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        for fut in as_completed(futs):
            out[futs[fut]] = fut.result()
    return out


def _job_val(item):
    seed, scorer = item
    set_scorer(scorer)
    return val_seed(int(seed))


def _job_test(it):
    seed, cap, prior, rearm, scorer = it
    set_scorer(scorer)
    return test_seed(int(seed), cap, prior, rearm)


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=os.getcwd(), text=True).strip()
    except Exception:
        return "unknown"


def write_tables(sel: dict) -> None:
    sp = spec()
    cap, prior = sel["cap"], sel["prior"]
    by_c1 = collect(cap, prior, "reset")
    by_q99 = collect("q99", "type", "reset")
    write_table1(sp.table1_tag, by_c1)
    write_fig_a(f"{sp.name}_reset", by_c1)
    write_fig_a(f"{sp.name}_reset_q99_type", by_q99)
    csvp = write_per_cell(sp.cell_tag, by_c1)
    write_per_cell(f"{sp.cell_tag}_q99_type", by_q99)
    write_evidence(sp.cell_tag, by_c1)
    write_standing(sp.cell_tag, cap, prior, "reset")
    if sp.name == "kairos":
        scale_table()
    pre = None
    pp = sp.log / "PRECHECK.json"
    if pp.is_file():
        pre = json.loads(pp.read_text(encoding="utf-8"))
    write_results(sel, by_c1, by_q99, csvp, pre)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorer", default="kairos", choices=["kairos", "orthrus", "velox"])
    ap.add_argument("--rearm", default="reset")
    ap.add_argument("--pair", default="selected,q99_type")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--datasets", default="CADETS_E3")
    ap.add_argument("--phase", default="all", choices=["val", "test", "tables", "all"])
    args = ap.parse_args(argv)
    if args.scorer == "velox":
        raise SystemExit("kairos_run is Kairos/ORTHRUS; VELOX uses firstalarm.run")
    set_scorer(args.scorer)
    if args.seeds == "0-4":
        seeds = list(SEEDS)
    else:
        seeds = [int(x) for x in args.seeds.split(",")]
    datasets = [x.strip() for x in args.datasets.split(",") if x.strip()]
    if any(d.startswith("THEIA") for d in datasets):
        print(f"v9 {args.scorer} THEIA 不跑；忽略 THEIA_*", flush=True)
    if DATASET not in datasets and datasets:
        print(f"只跑 {DATASET}", flush=True)
    rearms = [x.strip() for x in args.rearm.split(",") if x.strip()]
    if rearms != ["reset"]:
        print("强制 rearm=reset", flush=True)
        rearms = ["reset"]

    art = assert_write_path(spec().art)
    log = assert_write_path(spec().log)
    art.mkdir(parents=True, exist_ok=True)
    log.mkdir(parents=True, exist_ok=True)
    _append_runlog(
        f"\n# start phase={args.phase} scorer={args.scorer} rearm=reset seeds={seeds} "
        f"workers={args.workers} git={_git()} pid={os.getpid()}\n"
    )

    if args.phase in ("val", "all"):
        t0 = time.time()
        _parallel(_job_val, [(s, args.scorer) for s in seeds], args.workers)
        sel = choose_from_vals(seeds)
        _append_runlog(
            f"## val {time.time()-t0:.1f}s sel={sel['cap']}_{sel['prior']} mark={sel['mark']}\n"
        )
    else:
        p = spec().art / DATASET / "selection.json"
        sel = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"cap": "q99", "prior": "type", "mark": "missing"}

    pairs = []
    want = [x.strip() for x in args.pair.split(",") if x.strip()]
    if "selected" in want:
        pairs.append((sel["cap"], sel["prior"]))
    if "q99_type" in want or "q99+type" in want:
        pairs.append(("q99", "type"))
    uniq = []
    seen = set()
    for cap, prior in pairs:
        if (cap, prior) not in seen:
            seen.add((cap, prior))
            uniq.append((cap, prior))

    if args.phase in ("test", "all"):
        items = [(s, cap, prior, "reset", args.scorer) for cap, prior in uniq for s in seeds]
        t0 = time.time()
        _parallel(_job_test, items, args.workers)
        _append_runlog(f"## test n={len(items)} {time.time()-t0:.1f}s pairs={uniq}\n")

    if args.phase in ("tables", "all"):
        t0 = time.time()
        write_tables(sel)
        _append_runlog(f"## tables {time.time()-t0:.1f}s\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
