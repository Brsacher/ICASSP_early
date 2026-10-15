"""v9-3 report: python -m scripts.run_fa_v9_3 --phase all --workers 8"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from firstalarm.config import LOG_ROOT
from firstalarm.report_v93 import (
    alert_seed,
    collect_evals,
    load_selections,
    replay_timing,
    variant_specs,
    write_alert_appendix,
    write_evidence,
    write_fig_a_plots,
    write_tables,
)


def _append(text: str) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    with (LOG_ROOT / "RUN_LOG.md").open("a", encoding="utf-8") as f:
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


def _job_alert(it):
    ds, seed, cap, prior, rearm = it
    return alert_seed(ds, seed, cap, prior, rearm)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all", choices=["tables", "evidence", "alerts", "fig", "timing", "all"])
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    sels = load_selections()
    _append(f"\n# v9-3 start phase={args.phase} workers={args.workers} sel={ {d: (v['cap'], v['prior']) for d,v in sels.items()} }\n")

    if args.phase in ("tables", "all"):
        t0 = time.time()
        _checks, payload = write_tables(sels)
        _append(f"## tables {time.time()-t0:.1f}s pdf_d1_mismatch={len(payload['pdf_d1_mismatch'])} d1_cross={len(payload['d1_cross_variant'])}\n")
        if payload["pdf_d1_mismatch"]:
            print("D1 vs PDF mismatches:", payload["pdf_d1_mismatch"])
        if payload["d1_cross_variant"]:
            print("D1 cross-variant mismatches:", payload["d1_cross_variant"][:8])
        from firstalarm.config import ART_ROOT, V8_ART
        for ds in ("CADETS_E3", "THEIA_E3"):
            (LOG_ROOT / f"groundtruth_{ds}.json").write_bytes((V8_ART / ds / "groundtruth.json").read_bytes())
            (LOG_ROOT / f"selection_{ds}.json").write_bytes((ART_ROOT / ds / "selection.json").read_bytes())

    if args.phase in ("evidence", "all"):
        t0 = time.time()
        for tag, rearm, cap_by in variant_specs(sels):
            by = collect_evals(rearm, cap_by)
            write_evidence(tag, by)
        _append(f"## evidence {time.time()-t0:.1f}s\n")

    if args.phase in ("alerts", "all"):
        t0 = time.time()
        jobs = []
        seen = set()
        for tag, rearm, cap_by in variant_specs(sels):
            for ds, (cap, prior) in cap_by.items():
                for seed in range(5):
                    key = (ds, seed, cap, prior, rearm)
                    if key in seen:
                        continue
                    seen.add(key)
                    jobs.append(key)
        blobs = _parallel(_job_alert, jobs, args.workers)
        by_tag = {tag: [] for tag, _r, _c in variant_specs(sels)}
        for blob in blobs:
            for tag, rearm, cap_by in variant_specs(sels):
                cap, prior = cap_by[blob["dataset"]]
                if blob["rearm"] == rearm and blob["cap"] == cap and blob["prior"] == prior:
                    by_tag[tag].append(blob)
        for tag, rows in by_tag.items():
            write_alert_appendix(tag, rows)
        _append(f"## alerts n={len(jobs)} {time.time()-t0:.1f}s\n")

    if args.phase in ("fig", "all"):
        t0 = time.time()
        write_fig_a_plots("reset")
        _append(f"## figA {time.time()-t0:.1f}s\n")

    if args.phase in ("timing", "all"):
        t0 = time.time()
        rows = []
        for ds in ("CADETS_E3", "THEIA_E3"):
            cap, prior = sels[ds]["cap"], sels[ds]["prior"]
            rec = replay_timing(ds, 0, cap, prior, "reset")
            print(f"[timing] {ds} seed0 reset wall={rec['wall_s']:.2f}s ev/s={rec['events_per_s']:.0f}", flush=True)
            rows.append(rec)
        (LOG_ROOT / "timing_single.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        _append(f"## timing_single {time.time()-t0:.1f}s {[{r['dataset']: round(r['wall_s'],1)} for r in rows]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
