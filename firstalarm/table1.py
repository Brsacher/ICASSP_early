"""Table 1, fig A JSON, per-cell CSV, labels."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from firstalarm.config import ART_ROOT, BUDGETS, DATASETS, LOG_ROOT, PAPER_GROUP, RULES, SEEDS, TABLE_BUDGETS
from firstalarm.pipeline import load_eval


def _median(xs):
    """numpy.median: even count averages the two central values."""
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and not np.isfinite(x))]
    if not xs:
        return None
    return float(np.median(np.asarray(xs, dtype=np.float64)))


def label_attack(evals: list[dict], name: str) -> str:
    """v9-3: spike if ≥1 D1@h1(0) hit and median n_seen≤2; quiet if no hit or median ρ≥0.25; else mid."""
    seen = []
    rhos = []
    for ev in evals:
        e = ev["attacks"][name]["rows"]["0"]["D1"]
        if e.get("hit") and e.get("rho_e") is not None:
            if e.get("n_seen") is not None:
                seen.append(int(e["n_seen"]))
            rhos.append(float(e["rho_e"]))
    n_hit = len(rhos)
    is_spike = n_hit >= 1 and seen and _median(seen) is not None and _median(seen) <= 2
    is_quiet = n_hit == 0 or (rhos and _median(rhos) is not None and _median(rhos) >= 0.25)
    if is_spike and not is_quiet:
        return "spike-start"
    if is_quiet and not is_spike:
        return "quiet-start"
    if is_spike and is_quiet:
        return "mid"
    return "mid"


def collect_evals(rearm: str, cap_by_ds: dict[str, tuple[str, str]], seeds=SEEDS, datasets=None) -> dict[str, list[dict]]:
    out = {}
    for ds in (datasets or DATASETS):
        cap, prior = cap_by_ds[ds]
        out[ds] = [load_eval(ds, s, rearm, cap, prior) for s in seeds]
    return out


def cell_stats(evals: list[dict], name: str, b: int, rule: str) -> dict:
    hits = []
    fps = []
    for ev in evals:
        e = ev["attacks"][name]["rows"][str(b)][rule]
        fps.append(e.get("fp_day"))
        if e.get("hit"):
            hits.append(e)
    k = len(hits)
    n = len(evals)
    if not hits:
        return {
            "k": 0, "n": n, "rho": None, "d": None, "fp": _median(fps),
            "dagger": False, "rho_s": "miss", "d_s": "miss", "fp_s": _fmt_fp(_median(fps)),
        }
    rhos = [float(e["rho_e"]) for e in hits]
    ds = [float(e["delay_t0"]) for e in hits]
    rho = _median(rhos)
    d = _median(ds)
    fp = _median(fps)
    target = rho
    mid = min(hits, key=lambda e: (abs(float(e["rho_e"]) - target), e.get("tstar_str") or ""))
    dagger = mid.get("trig") == "nM" or mid.get("chain_has_M") is False
    return {
        "k": k, "n": n, "rho": rho, "d": d, "fp": fp,
        "dagger": dagger,
        "rho_s": _fmt_rho(rho),
        "d_s": _fmt_d(d),
        "fp_s": _fmt_fp(fp),
    }


def _fmt_rho(x):
    if x is None:
        return "miss"
    return f"{float(x):.2f}"


def _fmt_d(x):
    if x is None:
        return "miss"
    return f"{int(round(float(x)))}"


def _fmt_fp(x):
    if x is None:
        return "miss"
    v = float(x)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def earliness_of(evals: list[dict], b: int, rule: str) -> tuple[float, int, int]:
    xs = []
    n_miss = 0
    for ev in evals:
        for att in ev["attacks"].values():
            e = att["rows"][str(b)][rule]
            if e.get("hit") and e.get("rho_e") is not None:
                xs.append(1.0 - float(e["rho_e"]))
            else:
                xs.append(0.0)
                n_miss += 1
    return (float(np.mean(xs)) if xs else 0.0), n_miss, len(xs)


def f_median(evals: list[dict], b: int, rule: str) -> float:
    ys = [float(ev["c2"][str(b)][rule]["mean_B"]) for ev in evals]
    return float(np.median(np.asarray(ys, dtype=np.float64)))


def _fmt_rho_cell(st: dict, bold: bool) -> str:
    if st["k"] == 0:
        s = f"miss (0/{st['n']})"
    else:
        dag = "†" if st["dagger"] else ""
        s = f"{st['rho_s']}{dag} ({st['k']}/{st['n']})"
    return f"**{s}**" if bold else s


def _fmt_d_cell(st: dict, bold: bool) -> str:
    s = st["d_s"]
    return f"**{s}**" if bold else s


def _bold_plan(stats: dict[str, dict]) -> tuple[set[str], set[str]]:
    max_k = max(st["k"] for st in stats.values())
    if max_k <= 0:
        return set(), set()
    cands = [r for r, st in stats.items() if st["k"] == max_k]
    rhos = [(r, stats[r]["rho"]) for r in cands if stats[r]["rho"] is not None]
    ds = [(r, stats[r]["d"]) for r in cands if stats[r]["d"] is not None]
    bold_rho, bold_d = set(), set()
    if rhos:
        m = min(v for _r, v in rhos)
        bold_rho = {r for r, v in rhos if v == m}
    if ds:
        m = min(v for _r, v in ds)
        bold_d = {r for r, v in ds if v == m}
    return bold_rho, bold_d


def write_table1(tag: str, by_ds: dict[str, list[dict]], write_art: bool = False) -> tuple[Path, Path]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    blocks = {"quiet-start": [], "spike-start": [], "mid": []}
    labels = {}
    mismatches = []
    for ds, evals in by_ds.items():
        names = list(evals[0]["attacks"].keys())
        for name in names:
            lab = label_attack(evals, name)
            labels[(ds, name)] = lab
            paper = PAPER_GROUP.get(name)
            if paper and ((paper == "quiet" and lab != "quiet-start") or (paper == "spike" and lab != "spike-start")):
                mismatches.append({"dataset": ds, "attack": name, "p1": lab, "paper": paper})
            for b in TABLE_BUDGETS:
                stats = {r: cell_stats(evals, name, b, r) for r in RULES}
                br, bd = _bold_plan(stats)
                row = {
                    "dataset": ds, "attack": name, "b": b, "label": lab, "stats": stats,
                    "bold_rho": br, "bold_d": bd,
                }
                blocks[lab].append(row)

    lines = [f"# TABLE1_{tag}", ""]
    tex_rows = []
    show_rules = [("D1", "D1"), ("D2", "D2"), ("D3", "D3"), ("D4", "FirstAlarm")]
    header = ["dataset", "attack", "b"]
    for _k, lab in show_rules:
        header += [f"{lab} ρ (k/5)", f"{lab} d", f"{lab} FP"]
    for blk in ("quiet-start", "spike-start", "mid"):
        rows = blocks[blk]
        if not rows:
            continue
        lines.append(f"## {blk}")
        lines.append("")
        md = [header]
        for row in rows:
            line = [row["dataset"], row["attack"], str(row["b"])]
            tex = [row["dataset"].replace("_", "\\_"), row["attack"].replace("_", "\\_"), str(row["b"])]
            for rk, _lab in show_rules:
                st = row["stats"][rk]
                rs = _fmt_rho_cell(st, rk in row["bold_rho"])
                ds_ = _fmt_d_cell(st, rk in row["bold_d"])
                line += [rs, ds_, st["fp_s"]]
                tr = rs.replace("**", "\\textbf{").replace("†", "$\\dagger$")
                if "\\textbf{" in tr and not tr.endswith("}"):
                    # crude: wrap whole if both stars stripped poorly
                    tr = rs.replace("**", "")
                    if rk in row["bold_rho"]:
                        tr = f"\\textbf{{{tr}}}"
                td = st["d_s"]
                if rk in row["bold_d"]:
                    td = f"\\textbf{{{td}}}"
                tex += [tr.replace("†", "$\\dagger$") if "\\textbf" in tr else (rs.replace("**", "").replace("†", "$\\dagger$") if rk not in row["bold_rho"] else tr), td, st["fp_s"]]
            md.append(line)
            tex_rows.append(tex)
        lines.append(_md(md))
        lines.append("")

    lines.append("## bottom")
    lines.append("")
    bot = [["dataset", "metric", "b=2", "b=5"]]
    for ds, evals in by_ds.items():
        for b in TABLE_BUDGETS:
            pass
        e2, m2, n2 = earliness_of(evals, 2, "D4")
        e5, m5, n5 = earliness_of(evals, 5, "D4")
        f2 = f_median(evals, 2, "D4")
        f5 = f_median(evals, 5, "D4")
        bot.append([ds, "earliness D4 (n_miss)", f"{e2:.4f} ({m2})", f"{e5:.4f} ({m5})"])
        bot.append([ds, "F D4", f"{f2:.4f}", f"{f5:.4f}"])
        for rule in ("D1", "D2", "D3"):
            a2, mm2, _ = earliness_of(evals, 2, rule)
            a5, mm5, _ = earliness_of(evals, 5, rule)
            bot.append([ds, f"earliness {rule} (n_miss)", f"{a2:.4f} ({mm2})", f"{a5:.4f} ({mm5})"])
            bot.append([ds, f"F {rule}", f"{f_median(evals, 2, rule):.4f}", f"{f_median(evals, 5, rule):.4f}"])
    lines.append(_md(bot))
    lines.append("")
    if mismatches:
        lines.append("## label vs paper")
        lines.append("")
        lines.append(_md([["dataset", "attack", "P1", "paper"]] + [[x["dataset"], x["attack"], x["p1"], x["paper"]] for x in mismatches]))
        lines.append("")

    text = "\n".join(lines) + "\n"
    md_path = LOG_ROOT / f"TABLE1_{tag}.md"
    md_path.write_text(text, encoding="utf-8")
    tex_body = "\n".join(" & ".join(r) + " \\\\" for r in tex_rows) + "\n"
    tex_path = LOG_ROOT / f"TABLE1_{tag}.tex"
    tex_path.write_text(tex_body, encoding="utf-8")
    if write_art:
        ART_ROOT.mkdir(parents=True, exist_ok=True)
        (ART_ROOT / f"TABLE1_{tag}.md").write_text(text, encoding="utf-8")
        (ART_ROOT / f"TABLE1_{tag}.tex").write_text(tex_body, encoding="utf-8")
    return md_path, tex_path


def _md(rows: list[list]) -> str:
    if not rows:
        return ""
    head = "| " + " | ".join(str(x) for x in rows[0]) + " |"
    sep = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = ["| " + " | ".join(str(x) for x in r) + " |" for r in rows[1:]]
    return "\n".join([head, sep] + body)


def write_fig_a(tag: str, by_ds: dict[str, list[dict]], write_art: bool = False) -> list[Path]:
    paths = []
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    for ds, evals in by_ds.items():
        obj = {}
        for b in BUDGETS:
            obj[str(b)] = {}
            for rule in RULES:
                ear, n_miss, n = earliness_of(evals, int(b), rule)
                obj[str(b)][rule] = {
                    "earliness": ear,
                    "n_miss": n_miss,
                    "n": n,
                    "F_median": f_median(evals, int(b), rule),
                }
        p = LOG_ROOT / f"figA_{tag}_{ds}.json"
        p.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")
        paths.append(p)
        if write_art:
            ART_ROOT.mkdir(parents=True, exist_ok=True)
            (ART_ROOT / f"figA_{tag}_{ds}.json").write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")
    return paths


def write_per_cell(tag: str, by_ds: dict[str, list[dict]], write_art: bool = False) -> Path:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    path = LOG_ROOT / f"per_cell_{tag}.csv"
    ART_ROOT.mkdir(parents=True, exist_ok=True)
    fields = [
        "dataset", "attack", "seed", "b", "rule", "hit", "tstar", "flag",
        "rho", "delay", "fp_day", "channel", "trig", "chain_has_M",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for ds, evals in by_ds.items():
            for ev in evals:
                for name, att in ev["attacks"].items():
                    for b, row in att["rows"].items():
                        for rule in RULES:
                            e = row[rule]
                            w.writerow({
                                "dataset": ds,
                                "attack": name,
                                "seed": ev["seed"],
                                "b": b,
                                "rule": rule,
                                "hit": int(bool(e.get("hit"))),
                                "tstar": e.get("tstar_str") or "miss",
                                "flag": e.get("flag") or "",
                                "rho": "" if e.get("rho_e") is None else e["rho_e"],
                                "delay": "" if e.get("delay_t0") is None else e["delay_t0"],
                                "fp_day": e.get("fp_day"),
                                "channel": e.get("channel") or "",
                                "trig": e.get("trig") or "",
                                "chain_has_M": "" if e.get("chain_has_M") is None else int(bool(e["chain_has_M"])),
                            })
    if write_art:
        ART_ROOT.mkdir(parents=True, exist_ok=True)
        (ART_ROOT / f"per_cell_{tag}.csv").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def d1_cells(by_ds: dict[str, list[dict]]) -> dict:
    out = {}
    for ds, evals in by_ds.items():
        names = list(evals[0]["attacks"].keys())
        for name in names:
            for b in TABLE_BUDGETS:
                st = cell_stats(evals, name, b, "D1")
                out[(ds, name, b)] = (st["rho_s"], st["k"], st["d_s"], st["fp_s"])
    return out


def d1_mismatch(a: dict, b: dict) -> list:
    keys = sorted(set(a) | set(b))
    return [{"key": k, "a": a.get(k), "b": b.get(k)} for k in keys if a.get(k) != b.get(k)]


def earliness_from_csv(path: Path, dataset: str, b: int, rule: str) -> float:
    xs = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["dataset"] != dataset or int(row["b"]) != int(b) or row["rule"] != rule:
                continue
            if row["hit"] == "1" and row["rho"] != "":
                xs.append(1.0 - float(row["rho"]))
            else:
                xs.append(0.0)
    return float(np.mean(xs)) if xs else 0.0
