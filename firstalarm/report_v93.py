"""v9-3 report layer: evidence, paper tex, fig A, alert volume. Does not change rules/P1."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from firstalarm.alerts import alerted_procs_day, crossings
from firstalarm.config import (
    ART_ROOT,
    BUDGETS,
    DATASETS,
    LOG_ROOT,
    RULES,
    SEEDS,
    TABLE_BUDGETS,
    TEST_DATES,
    VAL_DATES,
)
from firstalarm.groundtruth import load_groundtruth
from firstalarm.lineage import load_lineage
from firstalarm.pipeline import _cr_mem, _priors_and_cap, load_eval, load_val
from firstalarm.rent import delta_on_stream
from firstalarm.rules import run_d2, run_d3
from firstalarm.stream import load_stream
from firstalarm.table1 import (
    _bold_plan,
    cell_stats,
    collect_evals,
    earliness_from_csv,
    earliness_of,
    f_median,
    label_attack,
    write_fig_a,
    write_per_cell,
    write_table1,
)
from firstalarm.timeutil import ns_to_datetime_us

ATTACK_SHORT = {
    "Nginx_Backdoor_06": "6 Apr",
    "Nginx_Backdoor_12": "12 Apr",
    "Nginx_Backdoor_13": "13 Apr",
    "Firefox_Backdoor_Drakon_In_Memory": "THEIA 10 Apr",
    "Browser_Extension_Drakon_Dropper": "THEIA 12 Apr",
}

PDF_D1 = {
    ("CADETS_E3", "Nginx_Backdoor_06", 2): ("0.24", "271"),
    ("CADETS_E3", "Nginx_Backdoor_06", 5): ("0.24", "271"),
    ("CADETS_E3", "Nginx_Backdoor_13", 5): ("0.06", "111"),
    ("THEIA_E3", "Firefox_Backdoor_Drakon_In_Memory", 2): ("0.31", "330"),
    ("THEIA_E3", "Firefox_Backdoor_Drakon_In_Memory", 5): ("0.31", "330"),
    ("THEIA_E3", "Browser_Extension_Drakon_Dropper", 2): ("0.01", "2"),
    ("THEIA_E3", "Browser_Extension_Drakon_Dropper", 5): ("0.01", "2"),
}

SHOW_RULES = [("D1", "D1"), ("D2", "D2"), ("D3", "D3"), ("D4", "FirstAlarm")]


def variant_specs(sels: dict) -> list[tuple[str, str, dict]]:
    """(tag, rearm, cap_by_ds)."""
    out = []
    for tag, rearm, fixed in (
        ("below", "below", None),
        ("reset", "reset", None),
        ("fir", "fir", None),
        ("reset_q99_kind", "reset", ("q99", "kind")),
    ):
        cap_by = {}
        for ds in DATASETS:
            cap_by[ds] = fixed if fixed else (sels[ds]["cap"], sels[ds]["prior"])
        out.append((tag, rearm, cap_by))
    return out


def load_selections() -> dict:
    out = {}
    for ds in DATASETS:
        p = ART_ROOT / ds / "selection.json"
        out[ds] = json.loads(p.read_text(encoding="utf-8"))
    return out


def write_tables(sels: dict, seeds=SEEDS):
    checks = []
    d1_by = {}
    labels = {}
    for tag, rearm, cap_by in variant_specs(sels):
        by = collect_evals(rearm, cap_by, seeds)
        write_table1(tag, by, write_art=False)
        write_fig_a(tag, by, write_art=False)
        csvp = write_per_cell(tag, by, write_art=False)
        for ds, evals in by.items():
            e2, _, _ = earliness_of(evals, 2, "D4")
            c2 = earliness_from_csv(csvp, ds, 2, "D4")
            if abs(e2 - c2) > 1e-12:
                raise RuntimeError(f"earliness mismatch {tag} {ds} b=2 {e2} vs csv {c2}")
            for name in evals[0]["attacks"]:
                labels[(tag, ds, name)] = label_attack(evals, name)
        d1_by[tag] = {}
        for ds, evals in by.items():
            for name in evals[0]["attacks"]:
                for b in TABLE_BUDGETS:
                    st = cell_stats(evals, name, b, "D1")
                    d1_by[tag][(ds, name, b)] = (st["rho_s"], st["d_s"], st["k"])
        if tag in ("reset", "below", "fir"):
            write_paper_tex(tag, by)
        checks.append((tag, by))
    pdf_mism = []
    ref = d1_by["reset"]
    for key, (want_rho, want_d) in PDF_D1.items():
        got = ref.get(key)
        if got is None or got[0] != want_rho or got[1] != want_d:
            pdf_mism.append({"key": key, "want": (want_rho, want_d), "got": got})
    cross = []
    for tag, cells in d1_by.items():
        if tag == "reset":
            continue
        for k, v in cells.items():
            if d1_by["reset"].get(k) != v:
                cross.append({"tag": tag, "key": k, "reset": d1_by["reset"].get(k), "other": v})
    payload = {"pdf_d1_mismatch": pdf_mism, "d1_cross_variant": cross, "labels": {f"{a}|{b}|{c}": v for (a, b, c), v in labels.items()}}
    (LOG_ROOT / "D1_PDF_CHECK.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return checks, payload


def write_paper_tex(tag: str, by_ds: dict) -> Path:
    blocks = {"quiet-start": [], "spike-start": [], "mid": []}
    for ds, evals in by_ds.items():
        for name in evals[0]["attacks"]:
            lab = label_attack(evals, name)
            for b in TABLE_BUDGETS:
                stats = {r: cell_stats(evals, name, b, r) for r in RULES}
                br, bd = _bold_plan(stats)
                blocks[lab].append({"dataset": ds, "attack": name, "b": b, "stats": stats, "bold_rho": br, "bold_d": bd})
    lines = [f"% TABLE1_{tag} paper tabular rows (v9-3)", "% columns: Attack, b, D1 ρ (k/5), d, FP, D2, D3, FirstAlarm"]
    for blk in ("quiet-start", "spike-start", "mid"):
        rows = blocks[blk]
        if not rows:
            continue
        lines.append(f"\\multicolumn{{14}}{{l}}{{\\textit{{{blk}}}}} \\\\")
        for row in rows:
            cells = [ATTACK_SHORT.get(row["attack"], row["attack"]).replace("_", "\\_"), str(row["b"])]
            for rk, _lab in SHOW_RULES:
                st = row["stats"][rk]
                if st["k"] == 0:
                    rho = "miss (0/5)"
                    d = "miss"
                else:
                    dag = "$^\\dagger$" if st["dagger"] else ""
                    rho = f"{st['rho_s']}{dag} ({st['k']}/{st['n']})"
                    d = st["d_s"]
                if rk in row["bold_rho"] and st["k"] > 0:
                    rho = f"\\textbf{{{rho}}}"
                if rk in row["bold_d"] and st["k"] > 0:
                    d = f"\\textbf{{{d}}}"
                cells += [rho, d, st["fp_s"]]
            lines.append(" & ".join(cells) + " \\\\")
    lines.append("% bottom")
    for ds, evals in by_ds.items():
        e2, m2, _ = earliness_of(evals, 2, "D4")
        e5, m5, _ = earliness_of(evals, 5, "D4")
        f2 = f_median(evals, 2, "D4")
        f5 = f_median(evals, 5, "D4")
        short = "CADETS" if ds.startswith("CADETS") else "THEIA"
        lines.append(
            f"{short} earliness (miss) & 2/5 & {e2:.4f} ({m2}) & {e5:.4f} ({m5}) \\\\"
        )
        lines.append(f"{short} F & 2/5 & {f2:.4f} & {f5:.4f} \\\\")
    path = LOG_ROOT / f"TABLE1_{tag}.tex"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_evidence(tag: str, by_ds: dict) -> Path:
    lines = [f"# EVIDENCE_{tag}", "", "D4 按胜出通道的 trig / chain_has_M。† = 链不含 M_i（D1 为触发事件 ∉ M_i）。", ""]
    table_hits = defaultdict(int)
    rows_out = []
    for ds, evals in by_ds.items():
        lines.append(f"## {ds}")
        lines.append("")
        lines.append("| rule | b | n_hit | n_chain_M | n_dagger |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for b in BUDGETS:
            for rule in RULES:
                n_hit = n_m = n_dag = 0
                for ev in evals:
                    for att in ev["attacks"].values():
                        e = att["rows"][str(b)][rule]
                        if not e.get("hit"):
                            continue
                        n_hit += 1
                        has = e.get("chain_has_M")
                        trig = e.get("trig")
                        if has is True or trig == "M":
                            n_m += 1
                        if has is False or trig == "nM":
                            n_dag += 1
                if int(b) in TABLE_BUDGETS:
                    table_hits[(ds, rule, int(b))] = n_hit
                lines.append(f"| {rule} | {b} | {n_hit} | {n_m} | {n_dag} |")
                rows_out.append({"dataset": ds, "rule": rule, "b": b, "n_hit": n_hit, "n_chain_M": n_m, "n_dagger": n_dag})
        lines.append("")
    lines.append("## b=2,5 summary")
    lines.append("")
    lines.append("| dataset | rule | b | n_hit | n_chain_M | n_dagger |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for r in rows_out:
        if int(r["b"]) in TABLE_BUDGETS:
            lines.append(f"| {r['dataset']} | {r['rule']} | {r['b']} | {r['n_hit']} | {r['n_chain_M']} | {r['n_dagger']} |")
    lines.append("")
    # vs table k sums
    lines.append("## vs TABLE1 k-sum")
    lines.append("")
    ok = True
    for ds, evals in by_ds.items():
        names = list(evals[0]["attacks"])
        for b in TABLE_BUDGETS:
            for rule in RULES:
                ksum = sum(cell_stats(evals, n, b, rule)["k"] for n in names)
                evn = table_hits[(ds, rule, int(b))]
                mark = "ok" if ksum == evn else "MISMATCH"
                if ksum != evn:
                    ok = False
                lines.append(f"- {ds} {rule} b={b}: evidence {evn} table_k_sum {ksum} {mark}")
    lines.append("")
    path = LOG_ROOT / f"EVIDENCE_{tag}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    if not ok:
        raise RuntimeError(f"EVIDENCE_{tag} hit counts != TABLE1 k sums")
    return path


def _avg_alerts(cr: dict, flagged: set[int]) -> float | None:
    if not flagged:
        return None
    return float(np.mean([len(cr.get(p, [])) for p in flagged]))


def alert_seed(dataset: str, seed: int, cap: str, prior: str, rearm: str) -> dict:
    """Replay test days; collect benign-proc mean alert counts and P_i pre-t0 lists."""
    print(f"[alert] {dataset} seed{seed} {rearm} {cap}_{prior}", flush=True)
    lin = load_lineage(dataset)
    gt = load_groundtruth(dataset)
    valj = load_val(dataset, seed)
    pair = valj["pairs"][f"{cap}_{prior}"]
    h1 = {int(k): float(v) for k, v in valj["h1"].items()}
    h2 = {int(k): float(v) for k, v in pair["h2"].items()}
    h3 = {int(k): float(v) for k, v in pair["h3"].items()}
    val = load_stream(dataset, seed, "val", VAL_DATES[dataset])
    pr, c, _mass = _priors_and_cap(val, prior)
    cap_c = None if cap == "none" else c
    del val
    daily = []
    pre = []
    for day in TEST_DATES[dataset]:
        es = load_stream(dataset, seed, "test", day)
        dlt = delta_on_stream(es, pr)
        S = es.s.astype(np.float64)
        day_atts = [a for a in gt.attacks if a.day == day]
        if rearm == "below":
            p2 = run_d2(es, pr, cap_c, lin, delta=dlt, rearm="below")
            p3 = run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm="below")
            for b in TABLE_BUDGETS:
                _record_alerts(daily, pre, es, S, p2, p3, h1, h2, h3, int(b), rearm, gt, day, day_atts, seed, dataset)
            del p2, p3
        else:
            for b in TABLE_BUDGETS:
                p2 = run_d2(es, pr, cap_c, lin, delta=dlt, rearm=rearm, h=h2[int(b)])
                p3 = run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm=rearm, h=h3[int(b)])
                _record_alerts(daily, pre, es, S, p2, p3, h1, h2, h3, int(b), rearm, gt, day, day_atts, seed, dataset)
                del p2, p3
        del es, S, dlt
    return {"dataset": dataset, "seed": seed, "rearm": rearm, "cap": cap, "prior": prior, "daily": daily, "pre_t0": pre}


def _record_alerts(daily, pre, es, S, p2, p3, h1, h2, h3, b, rearm, gt, day, day_atts, seed, dataset):
    cr1 = crossings(es, S, h1[int(b)], True)
    cr10 = crossings(es, S, h1[0], True)
    cr2 = _cr_mem(es, p2, h2[int(b)], False, rearm)
    cr3 = _cr_mem(es, p3, h3[int(b)], False, rearm)
    cr4 = {}
    for src in (cr10, cr3):
        for p, evs in src.items():
            cr4.setdefault(p, []).extend(evs)
    for p in cr4:
        cr4[p].sort(key=lambda x: x[1])
    for rule, cr in (("D1", cr1), ("D2", cr2), ("D3", cr3), ("D4", cr4)):
        flagged = alerted_procs_day(cr, gt.window_0411, day) - set(gt.gt_procs)
        daily.append({
            "dataset": dataset, "seed": seed, "day": day, "b": b, "rule": rule,
            "n_flagged_benign": len(flagged),
            "mean_alerts": _avg_alerts(cr, flagged),
            "n_alert_events": int(sum(len(cr.get(p, [])) for p in flagged)),
        })
    for a in day_atts:
        for rule, cr in (("D2", cr2), ("D3", cr3)):
            for p in sorted(a.P):
                evs = [(i, t) for i, t in cr.get(p, []) if t < a.t0]
                pre.append({
                    "dataset": dataset, "seed": seed, "attack": a.name, "day": a.day,
                    "b": b, "rule": rule, "proc": p, "n_pre": len(evs),
                    "times": [ns_to_datetime_us(t) for _i, t in evs],
                })


def write_alert_appendix(tag: str, blobs: list[dict]) -> None:
    path = LOG_ROOT / f"DIAG_standing_{tag}.md"
    old = path.read_text(encoding="utf-8") if path.is_file() else f"# DIAG_standing_{tag}\n"
    if "## alert volume" in old:
        old = old.split("## alert volume")[0].rstrip() + "\n\n"
    lines = [old, "## alert volume", "", "被标记良性进程 = `alerted_procs_day` 减去 GT 攻击进程。均值是这些进程上的告警次数平均（reset/fir 可 >1）。", ""]
    lines += ["### 测试日 · 良性进程平均告警次数", ""]
    lines += ["| dataset | seed | day | b | rule | n_flagged | mean_alerts | n_alert_events |"]
    lines += ["| --- | ---: | --- | ---: | --- | ---: | ---: | ---: |"]
    for blob in blobs:
        for r in blob["daily"]:
            ma = "" if r["mean_alerts"] is None else f"{r['mean_alerts']:.3f}"
            lines.append(
                f"| {r['dataset']} | {blob['seed']} | {r['day']} | {r['b']} | {r['rule']} | "
                f"{r['n_flagged_benign']} | {ma} | {r['n_alert_events']} |"
            )
    lines += ["", "### P_i 在 t0 前的告警（D2/D3，b∈{2,5}）", ""]
    lines += ["| dataset | seed | attack | b | rule | proc | n_pre | times |"]
    lines += ["| --- | ---: | --- | ---: | --- | ---: | ---: | --- |"]
    for blob in blobs:
        for r in blob["pre_t0"]:
            if r["n_pre"] == 0:
                continue
            times = ", ".join(r["times"][:12])
            if len(r["times"]) > 12:
                times += f" …(+{len(r['times'])-12})"
            lines.append(
                f"| {r['dataset']} | {blob['seed']} | {r['attack']} | {r['b']} | {r['rule']} | "
                f"{r['proc']} | {r['n_pre']} | {times} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_fig_a_plots(tag: str = "reset") -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths = []
    csv_path = LOG_ROOT / f"figA_{tag}_plotdata.csv"
    rows = []
    for ds in DATASETS:
        obj = json.loads((LOG_ROOT / f"figA_{tag}_{ds}.json").read_text(encoding="utf-8"))
        fig, ax = plt.subplots(figsize=(3.3, 2.55))
        styles = {
            "D1": dict(linestyle="-", marker="o", label="D1", color="C0"),
            "D4": dict(linestyle="-", marker="s", label="FirstAlarm", color="C1"),
            "D3": dict(linestyle="--", marker="^", label="D3", color="C2"),
        }
        for rule, sty in styles.items():
            xs, ys, labs = [], [], []
            for b in BUDGETS:
                rec = obj[str(b)]["D4" if rule == "D4" else rule]
                F = float(rec["F_median"])
                ear = float(rec["earliness"])
                rows.append({"dataset": ds, "b": b, "rule": "FirstAlarm" if rule == "D4" else rule,
                             "F": F, "earliness": ear, "n_miss": rec["n_miss"], "n": rec["n"]})
                if F <= 0:
                    continue
                xs.append(F)
                ys.append(ear)
                labs.append(str(b))
            ax.plot(xs, ys, **sty, linewidth=1.2, markersize=4)
            for x, y, lab in zip(xs, ys, labs):
                ax.annotate(lab, (x, y), textcoords="offset points", xytext=(3, 3), fontsize=8)
        ax.set_xscale("log")
        ax.set_xlabel("F", fontsize=8)
        ax.set_ylabel("earliness", fontsize=8)
        ax.tick_params(labelsize=8)
        ax.legend(fontsize=8, frameon=False)
        ax.set_title(ds.replace("_", " "), fontsize=8)
        fig.tight_layout()
        short = "CADETS" if ds.startswith("CADETS") else "THEIA"
        pdf = LOG_ROOT / f"figA_{tag}_{short}.pdf"
        fig.savefig(pdf, dpi=200, bbox_inches="tight")
        plt.close(fig)
        paths.append(pdf)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dataset", "b", "rule", "F", "earliness", "n_miss", "n"])
        w.writeheader()
        w.writerows(rows)
    paths.append(csv_path)
    return paths


def replay_timing(dataset: str, seed: int, cap: str, prior: str, rearm: str) -> dict:
    """Single-process test-day replay wall (W only, no eval)."""
    import time as _time
    lin = load_lineage(dataset)
    valj = load_val(dataset, seed)
    pair = valj["pairs"][f"{cap}_{prior}"]
    h2 = {int(k): float(v) for k, v in pair["h2"].items()}
    h3 = {int(k): float(v) for k, v in pair["h3"].items()}
    val = load_stream(dataset, seed, "val", VAL_DATES[dataset])
    pr, c, _m = _priors_and_cap(val, prior)
    cap_c = None if cap == "none" else c
    del val
    t0 = _time.perf_counter()
    n_ev = 0
    for day in TEST_DATES[dataset]:
        es = load_stream(dataset, seed, "test", day)
        n_ev += es.n
        dlt = delta_on_stream(es, pr)
        if rearm == "below":
            run_d2(es, pr, cap_c, lin, delta=dlt, rearm="below")
            run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm="below")
        else:
            for b in BUDGETS:
                run_d2(es, pr, cap_c, lin, delta=dlt, rearm=rearm, h=h2[int(b)])
                run_d3(es, pr, cap_c, lin, True, delta=dlt, rearm=rearm, h=h3[int(b)])
        del es, dlt
    wall = _time.perf_counter() - t0
    return {
        "dataset": dataset, "seed": seed, "rearm": rearm, "cap": cap, "prior": prior,
        "workers": 1, "wall_s": wall, "n_events": n_ev,
        "events_per_s": (n_ev / wall) if wall > 0 else 0.0,
        "note": "single process; all test days; reset/fir replay all b",
    }
