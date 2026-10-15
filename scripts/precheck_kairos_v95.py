"""v9-5 / v9-8 前置检查：seed 隔离、全量 key 对齐、分数健全性。失败退出码 2。"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from firstalarm.config import REPO
from firstalarm.kairos_align import (
    align_split,
    all_days,
    attach_to_v8,
    clear_align_cache,
    save_stream_cache,
)
from firstalarm.kairos_config import DATASET, PREREG_COMMIT, SEEDS, set_scorer, spec
from firstalarm.kairos_paths import csvs, get_scorer_paths, load_scorer_summary
from firstalarm.stream import load_stream


def _md5(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_isolation(summary: dict) -> dict:
    trains = []
    for run in summary["runs"]:
        if run["dataset"] != DATASET:
            continue
        trains.append((int(run["seed"]), run["paths"]["training"]))
    trains.sort()
    uniq = len({t for _s, t in trains}) == len(trains)
    val_name = test_name = None
    md5s = {}
    for seed, _t in trains:
        kr = get_scorer_paths(seed)
        vn = [p.name for p in csvs(kr, "val")]
        tn = [p.name for p in csvs(kr, "test")]
        if val_name is None:
            val_name, test_name = vn[0], tn[0]
        md5s[seed] = {
            "val_file": val_name,
            "val_md5": _md5(next(p for p in csvs(kr, "val") if p.name == val_name)),
            "test_file": test_name,
            "test_md5": _md5(next(p for p in csvs(kr, "test") if p.name == test_name)),
        }
    pairs_same = []
    for a in range(len(trains)):
        for b in range(a + 1, len(trains)):
            sa, sb = trains[a][0], trains[b][0]
            if md5s[sa]["val_md5"] == md5s[sb]["val_md5"]:
                pairs_same.append(("val", sa, sb))
            if md5s[sa]["test_md5"] == md5s[sb]["test_md5"]:
                pairs_same.append(("test", sa, sb))
    ok = uniq and not pairs_same and len(trains) == 5
    return {
        "ok": ok,
        "n_runs": len(trains),
        "training_unique": uniq,
        "training": [t for _s, t in trains],
        "md5s": {str(k): v for k, v in md5s.items()},
        "same_md5_pairs": pairs_same,
    }


def _quant(x: np.ndarray) -> dict:
    x = x[np.isfinite(x)]
    return {
        "min": float(x.min()) if x.size else None,
        "q50": float(np.quantile(x, 0.5)) if x.size else None,
        "q99": float(np.quantile(x, 0.99)) if x.size else None,
        "q99.9": float(np.quantile(x, 0.999)) if x.size else None,
        "max": float(x.max()) if x.size else None,
        "n": int(x.size),
        "n_nan": 0,
        "n_neg": int((x < 0).sum()) if x.size else 0,
        "n_inf": 0,
    }


def check_prereg() -> dict:
    """Recorded fact, not a live git diff.

    The ORTHRUS criterion was committed as 2913926 on 2026-09-20 05:02:38 -0400,
    before that training run. See docs/PREREGISTRATION.md. This tree is not the
    lab git checkout, so there is nothing to diff.
    """
    return {
        "ok": True,
        "commit": PREREG_COMMIT,
        "note": "see docs/PREREGISTRATION.md; no git diff in the public tree",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorer", default="kairos", choices=["kairos", "orthrus"])
    args = ap.parse_args(argv)
    set_scorer(args.scorer)
    log = spec().log
    log.mkdir(parents=True, exist_ok=True)
    spec().art.mkdir(parents=True, exist_ok=True)
    prereg = check_prereg() if args.scorer == "orthrus" else {"ok": True, "commit": None, "skipped": True}
    if args.scorer == "orthrus" and not prereg["ok"]:
        print(f"[precheck] PROTOCOL_v9.md changed since {PREREG_COMMIT}", flush=True)
    summary = load_scorer_summary()
    iso = check_isolation(summary)
    print(f"[precheck] isolation ok={iso['ok']}", flush=True)
    align = []
    sane = []
    attach_ok = True
    for seed in SEEDS:
        print(f"[precheck] seed{seed} align…", flush=True)
        seed_sane = {"seed": seed, "days": {}}
        splits = {}
        for split, _day in all_days():
            if split not in splits:
                print(f"  reading {split} windows…", flush=True)
                splits[split] = align_split(seed, split)
        for split, day in all_days():
            if day not in splits[split]:
                rec = {"split": split, "day": day, "ok": False, "err": "missing day"}
                align.append({"seed": seed, **rec})
                attach_ok = False
                print(f"  {split} {day} MISSING", flush=True)
                continue
            al = splits[split][day]
            q = _quant(al.s_k)
            q["n_nan"] = int((~np.isfinite(al.s_k)).sum())
            q["n_inf"] = int(np.isinf(al.s_k).sum()) if al.s_k.size else 0
            day_ok = (
                al.unmatched == 0
                and al.multi_eq
                and q["n_nan"] == 0
                and q["n_neg"] == 0
                and q["n_inf"] == 0
            )
            rec = {
                "split": split,
                "day": day,
                "n": al.n,
                "unmatched": al.unmatched,
                "mode": al.mode,
                "dup_frac": al.n_dup_frac_k,
                "dup_frac_v": al.n_dup_frac_v,
                "multiset_eq": al.multi_eq,
                "loss": q,
                "ok": day_ok,
            }
            try:
                es = load_stream(DATASET, seed, split, day)
                attached = attach_to_v8(es, al)
                save_stream_cache(attached)
                rec["stream_n"] = es.n
                rec["attach_n"] = attached.n
                rec["attach_ok"] = True
            except Exception as e:  # noqa: BLE001
                rec["attach_ok"] = False
                rec["attach_err"] = str(e)
                attach_ok = False
                day_ok = False
            rec["ok"] = day_ok and rec.get("attach_ok", False)
            align.append({"seed": seed, **rec})
            seed_sane["days"][f"{split}_{day}"] = q
            print(
                f"  {split} {day} n={al.n} unmatched={al.unmatched} multi={al.multi_eq} "
                f"dup={al.n_dup_frac_k:.4f} mode={al.mode} attach={rec.get('attach_ok')} ok={rec['ok']}",
                flush=True,
            )
        clear_align_cache()
        sane.append(seed_sane)

    # 10x flag vs other seeds (any day, q50 or max); mark only, do not drop
    marked = []
    day_keys = sorted({k for row in sane for k in row["days"]})
    scale_detail = {}
    for day in day_keys:
        q50s = {row["seed"]: row["days"][day]["q50"] for row in sane if day in row["days"] and row["days"][day].get("q50") is not None}
        maxs = {row["seed"]: row["days"][day]["max"] for row in sane if day in row["days"] and row["days"][day].get("max") is not None}
        scale_detail[day] = {"q50": q50s, "max": maxs}
        for label, mp in (("q50", q50s), ("max", maxs)):
            if len(mp) < 2:
                continue
            med = float(np.median(list(mp.values())))
            if med <= 0:
                continue
            for s, v in mp.items():
                if v / med >= 10 or med / v >= 10:
                    marked.append(s)
    marked = sorted(set(marked))
    val_q50 = {row["seed"]: (row["days"].get("val_2018-04-10") or {}).get("q50") for row in sane}
    align_ok = all(r["ok"] for r in align)
    ok = bool(iso["ok"] and align_ok and attach_ok and prereg["ok"])
    out = {
        "ok": ok,
        "scorer": args.scorer,
        "prereg": prereg,
        "isolation": iso,
        "align": align,
        "sanity": sane,
        "scale_10x_seeds": marked,
        "scale_detail": {d: {"q50": {str(k): v for k, v in x["q50"].items()}, "max": {str(k): v for k, v in x["max"].items()}} for d, x in scale_detail.items()},
        "val_q50": {str(k): v for k, v in val_q50.items()},
    }
    path = log / "PRECHECK.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    title = "PRECHECK v9-8" if args.scorer == "orthrus" else "PRECHECK v9-5"
    md = [f"# {title}", "", f"ok={ok} scorer={args.scorer}", "", "## isolation", "",
          f"- training_unique={iso['training_unique']} n_runs={iso['n_runs']}",
          f"- same_md5_pairs={iso['same_md5_pairs']}", "",
          "## prereg", "", f"- {prereg}", "",
          "## align / sanity", "",
          "| seed | split | day | n | unmatched | multi | dup_frac | mode | min | q50 | q99 | q99.9 | max | ok |",
          "| ---: | --- | --- | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for r in align:
        loss = r.get("loss") or {}
        md.append(
            f"| {r.get('seed')} | {r.get('split')} | {r.get('day')} | {r.get('n')} | {r.get('unmatched')} | "
            f"{r.get('multiset_eq')} | {r.get('dup_frac')} | {r.get('mode')} | "
            f"{loss.get('min')} | {loss.get('q50')} | {loss.get('q99')} | {loss.get('q99.9')} | {loss.get('max')} | {r.get('ok')} |"
        )
    md += ["", "## 10× 标记（不剔除）", "", f"{marked}", ""]
    (log / "PRECHECK.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[precheck] ok={ok} wrote {path} 10x={marked}", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
