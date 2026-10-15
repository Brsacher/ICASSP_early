"""v9-5 reports → ecpg_reports/v9-5. Does not write fa/v9."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from firstalarm.config import BUDGETS, PAPER_GROUP, RULES, TABLE_BUDGETS, VAL_DATES
from firstalarm.groundtruth import load_groundtruth, mi_indices
from firstalarm.kairos_align import load_kairos_stream
from firstalarm.kairos_config import DATASET, KAIROS_ART, KAIROS_LOG, SEEDS, assert_write_path, spec
from firstalarm.kairos_pipeline import load_eval, load_val
from firstalarm.rent import build_priors, cap_q99, delta_on_stream
from firstalarm.stream import load_stream
from firstalarm.table1 import (
    _bold_plan,
    _fmt_d_cell,
    _fmt_rho_cell,
    _md,
    cell_stats,
    earliness_from_csv,
    earliness_of,
    f_median,
    label_attack,
)

def _log() -> Path:
    p = spec().log
    p.mkdir(parents=True, exist_ok=True)
    return p


def collect(cap: str, prior: str, rearm: str = "reset") -> dict[str, list[dict]]:
    return {DATASET: [load_eval(s, rearm, cap, prior) for s in SEEDS]}


def write_table1(tag: str, by: dict) -> tuple[Path, Path]:
    log = _log()
    blocks = {"quiet-start": [], "spike-start": [], "mid": []}
    mismatches = []
    for ds, evals in by.items():
        for name in evals[0]["attacks"]:
            lab = label_attack(evals, name)
            paper = PAPER_GROUP.get(name)
            if paper and ((paper == "quiet" and lab != "quiet-start") or (paper == "spike" and lab != "spike-start")):
                mismatches.append({"dataset": ds, "attack": name, "p1": lab, "paper": paper})
            for b in TABLE_BUDGETS:
                stats = {r: cell_stats(evals, name, b, r) for r in RULES}
                br, bd = _bold_plan(stats)
                blocks[lab].append({
                    "dataset": ds, "attack": name, "b": b, "label": lab, "stats": stats,
                    "bold_rho": br, "bold_d": bd,
                })
    lines = [f"# TABLE1_{tag}", ""]
    show_rules = [("D1", "D1"), ("D2", "D2"), ("D3", "D3"), ("D4", "FirstAlarm")]
    header = ["dataset", "attack", "b"]
    for _k, lab in show_rules:
        header += [f"{lab} ρ (k/5)", f"{lab} d", f"{lab} FP"]
    tex_rows = []
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
                tr = rs.replace("**", "")
                if rk in row["bold_rho"]:
                    tr = f"\\textbf{{{tr}}}"
                td = st["d_s"]
                if rk in row["bold_d"]:
                    td = f"\\textbf{{{td}}}"
                tex += [tr.replace("†", "$\\dagger$"), td, st["fp_s"]]
            md.append(line)
            tex_rows.append(tex)
        lines.append(_md(md))
        lines.append("")
    lines.append("## bottom")
    lines.append("")
    bot = [["dataset", "metric", "b=2", "b=5"]]
    for ds, evals in by.items():
        e2, m2, _ = earliness_of(evals, 2, "D4")
        e5, m5, _ = earliness_of(evals, 5, "D4")
        bot.append([ds, "earliness D4 (n_miss)", f"{e2:.4f} ({m2})", f"{e5:.4f} ({m5})"])
        bot.append([ds, "F D4", f"{f_median(evals, 2, 'D4'):.4f}", f"{f_median(evals, 5, 'D4'):.4f}"])
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
    md_path = assert_write_path(log / f"TABLE1_{tag}.md")
    tex_path = assert_write_path(log / f"TABLE1_{tag}.tex")
    md_path.write_text(text, encoding="utf-8")
    tex_path.write_text("\n".join(" & ".join(r) + " \\\\" for r in tex_rows) + "\n", encoding="utf-8")
    return md_path, tex_path


def write_fig_a(tag: str, by: dict) -> Path:
    ds, evals = DATASET, by[DATASET]
    obj = {}
    rows = []
    for b in BUDGETS:
        obj[str(b)] = {}
        for rule in RULES:
            ear, n_miss, n = earliness_of(evals, int(b), rule)
            rec = {"earliness": ear, "n_miss": n_miss, "n": n, "F_median": f_median(evals, int(b), rule)}
            obj[str(b)][rule] = rec
            rows.append({
                "dataset": ds, "b": b, "rule": "FirstAlarm" if rule == "D4" else rule,
                "F": rec["F_median"], "earliness": ear, "n_miss": n_miss, "n": n,
            })
    p = assert_write_path(_log() / f"figA_{tag}_{ds}.json")
    p.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")
    csvp = assert_write_path(_log() / f"figA_{tag}_plotdata.csv")
    with csvp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dataset", "b", "rule", "F", "earliness", "n_miss", "n"])
        w.writeheader()
        w.writerows(rows)
    return p


def write_per_cell(tag: str, by: dict) -> Path:
    path = assert_write_path(_log() / f"per_cell_{tag}.csv")
    fields = [
        "dataset", "attack", "seed", "b", "rule", "hit", "tstar", "flag",
        "rho", "delay", "fp_day", "channel", "trig", "chain_has_M",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for ds, evals in by.items():
            for ev in evals:
                for name, att in ev["attacks"].items():
                    for b, row in att["rows"].items():
                        for rule in RULES:
                            e = row[rule]
                            w.writerow({
                                "dataset": ds, "attack": name, "seed": ev["seed"], "b": b, "rule": rule,
                                "hit": int(bool(e.get("hit"))), "tstar": e.get("tstar_str") or "miss",
                                "flag": e.get("flag") or "",
                                "rho": "" if e.get("rho_e") is None else e["rho_e"],
                                "delay": "" if e.get("delay_t0") is None else e["delay_t0"],
                                "fp_day": e.get("fp_day"), "channel": e.get("channel") or "",
                                "trig": e.get("trig") or "",
                                "chain_has_M": "" if e.get("chain_has_M") is None else int(bool(e["chain_has_M"])),
                            })
    return path


def write_evidence(tag: str, by: dict) -> Path:
    lines = [f"# EVIDENCE_{tag}", "", "D4 按胜出通道的 trig / chain_has_M。† = 链不含 M_i（D1 为触发事件 ∉ M_i）。", ""]
    table_hits = defaultdict(int)
    rows_out = []
    for ds, evals in by.items():
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
    lines.append("## vs TABLE1 k-sum")
    lines.append("")
    ok = True
    for ds, evals in by.items():
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
    path = assert_write_path(_log() / f"EVIDENCE_{tag}.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    if not ok:
        raise RuntimeError(f"EVIDENCE_{tag} hit counts != TABLE1 k sums")
    return path


def write_standing(tag: str, cap: str, prior: str, rearm: str = "reset") -> Path:
    lines = [f"# DIAG_standing_{tag}", "", f"rearm={rearm} cap={cap} prior={prior}", ""]
    for seed in SEEDS:
        ev = load_eval(seed, rearm, cap, prior)
        for name, att in ev["attacks"].items():
            b = 5
            h3 = float(ev["h3"][str(b)])
            lines.append(f"### seed{seed} {name} day={att['day']} b={b} h3={h3}")
            lines.append("")
            lines.append("| proc | first_W_ge_h3 | W_mem/h @ t0 | n_alert_before_t0 | first_in_window | W_min | W_max |")
            lines.append("| ---: | --- | ---: | ---: | --- | ---: | ---: |")
            rows = (ev.get("standing") or {}).get(name, {}).get(str(b), {})
            for p in att["P"]:
                r = rows.get(str(p), {})
                ratio = r.get("w_over_h_t0")
                rs = "" if ratio is None else f"{float(ratio):.4g}"
                lo, hi = r.get("W_min"), r.get("W_max")
                lo_s = "" if lo is None else f"{float(lo):.4g}"
                hi_s = "" if hi is None else f"{float(hi):.4g}"
                lines.append(
                    f"| {p} | {r.get('first_W_ge_h3', '')} | {rs} | "
                    f"{r.get('n_alert_before_t0', '')} | {r.get('first_in_window', '')} | {lo_s} | {hi_s} |"
                )
            lines.append("")
    lines.append("## nginx A1/A2 b=5（P_i 最早越阈）")
    lines.append("")
    lines.append("| seed | attack | day | proc | first_W_ge_h3 | W/h @ t0 | n_alert_before_t0 |")
    lines.append("| ---: | --- | --- | ---: | --- | ---: | ---: |")
    for seed in SEEDS:
        ev = load_eval(seed, rearm, cap, prior)
        for name, day in (("Nginx_Backdoor_12", "2018-04-12"), ("Nginx_Backdoor_13", "2018-04-13")):
            att = ev["attacks"][name]
            rows = (ev.get("standing") or {}).get(name, {}).get("5", {})
            best = None
            for p in att["P"]:
                r = rows.get(str(p), {})
                first = r.get("first_W_ge_h3") or "none"
                rec = (first, p, r)
                if first != "none" and (best is None or first < best[0]):
                    best = rec
            if best is None:
                lines.append(f"| {seed} | {name} | {day} |  | none |  |  |")
            else:
                first, p, r = best
                ratio = r.get("w_over_h_t0")
                rs = "" if ratio is None else f"{float(ratio):.4g}"
                lines.append(f"| {seed} | {name} | {day} | {p} | {first} | {rs} | {r.get('n_alert_before_t0', '')} |")
    lines.append("")
    path = assert_write_path(_log() / f"DIAG_standing_{tag}.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def decompose(by: dict) -> dict:
    evals = by[DATASET]
    names = list(evals[0]["attacks"])
    out = {}
    for other_b, key in ((5, "vs_d1_b5"), (20, "vs_d1_b20"), (0, "vs_d1_b0")):
        both = fa_only = d1_only = none = 0
        rho_fa, rho_d1, rho_both_fa, rho_both_d1 = [], [], [], []
        for ev in evals:
            for name in names:
                fa = ev["attacks"][name]["rows"]["5"]["D4"]
                d1 = ev["attacks"][name]["rows"][str(other_b)]["D1"]
                hf, hd = bool(fa.get("hit")), bool(d1.get("hit"))
                if hf and hd:
                    both += 1
                    if fa.get("rho_e") is not None:
                        rho_both_fa.append(float(fa["rho_e"]))
                    if d1.get("rho_e") is not None:
                        rho_both_d1.append(float(d1["rho_e"]))
                elif hf:
                    fa_only += 1
                    if fa.get("rho_e") is not None:
                        rho_fa.append(float(fa["rho_e"]))
                elif hd:
                    d1_only += 1
                    if d1.get("rho_e") is not None:
                        rho_d1.append(float(d1["rho_e"]))
                else:
                    none += 1
        def _m(xs):
            return None if not xs else float(np.mean(xs))
        out[key] = {
            "both": both, "fa_only": fa_only, "d1_only": d1_only, "none": none,
            "mean_rho_fa_only": _m(rho_fa),
            "mean_rho_d1_only": _m(rho_d1),
            "mean_rho_both_fa": _m(rho_both_fa),
            "mean_rho_both_d1": _m(rho_both_d1),
            "mean_rho_fa_detected": _m(rho_fa + rho_both_fa),
            "mean_rho_d1_detected": _m(rho_d1 + rho_both_d1),
        }
    return out


def verdict(evals: list[dict]) -> dict:
    e_fa, _, _ = earliness_of(evals, 5, "D4")
    e_d1, _, _ = earliness_of(evals, 5, "D1")
    f_fa = f_median(evals, 5, "D4")
    f_d1_20 = f_median(evals, 20, "D1")
    gain = (e_fa - e_d1) >= 0.1 and f_fa <= f_d1_20
    return {
        "E_FA_b5": e_fa,
        "E_D1_b5": e_d1,
        "dE": e_fa - e_d1,
        "F_FA_b5": f_fa,
        "F_D1_b20": f_d1_20,
        "success": bool(gain),
        "label": "success" if gain else "no-gain",
    }


def scale_table(seeds=SEEDS) -> Path:
    """Val-day Kairos vs VELOX (v8 stream.s) δ_prog / cap / h."""
    lines = ["# scale_kairos_vs_velox", "", "验证日 2018-04-10。VELOX 列来自只读 v8 stream（不写 fa/v9）。", ""]
    rows = []
    for seed in seeds:
        kv = load_val(seed)
        k_es = load_kairos_stream(seed, "val", VAL_DATES[DATASET])
        v_es = load_stream(DATASET, seed, "val", VAL_DATES[DATASET])
        # selected pair from this seed's val (priors)
        # use type prior for cap (q99+type always reported) and kind for δ_prog names
        pr_k = build_priors(k_es, "kind")
        pr_v = build_priors(v_es, "kind")
        dlt_k = delta_on_stream(k_es, pr_k)
        dlt_v = delta_on_stream(v_es, pr_v)
        c_k, _ = cap_q99(k_es, dlt_k)
        c_v, _ = cap_q99(v_es, dlt_v)
        # per-program mean δ
        def prog_delta(es, dlt):
            acc = defaultdict(list)
            for i in range(es.n):
                acc[str(es.kind[i])].append(float(dlt[i]))
            cnt = {k: len(v) for k, v in acc.items()}
            top = sorted(cnt, key=lambda k: -cnt[k])[:10]
            means = {p: float(np.mean(vs)) for p, vs in acc.items()}
            return means, top
        dk, topk = prog_delta(k_es, dlt_k)
        dv, topv = prog_delta(v_es, dlt_v)
        top = ["nginx"] + [p for p in topk if p != "nginx"]
        for p in topv:
            if p not in top:
                top.append(p)
        top = top[:11]
        h1k = float(kv["h1"]["0"])
        from firstalarm.calibrate import calib_from_stat
        h1v = float(calib_from_stat(v_es, v_es.s)[0])
        selp = json.loads((spec().art / DATASET / "selection.json").read_text(encoding="utf-8"))
        c1_tag = f"{selp['cap']}_{selp['prior']}"
        h3k_c1 = float(kv["pairs"][c1_tag]["h3"]["5"])
        h3k_q99 = float(kv["pairs"]["q99_type"]["h3"]["5"])
        from firstalarm.rules import run_d3
        from firstalarm.lineage import load_lineage
        lin = load_lineage(DATASET)
        pr_vt = build_priors(v_es, "type")
        dlt_vt = delta_on_stream(v_es, pr_vt)
        c_vt, _ = cap_q99(v_es, dlt_vt)
        p3v_t = run_d3(v_es, pr_vt, c_vt, lin, True, delta=dlt_vt, rearm="below")
        h3v_q99 = float(calib_from_stat(v_es, p3v_t.W)[5])
        pr_vk = build_priors(v_es, selp["prior"])
        dlt_vk = delta_on_stream(v_es, pr_vk)
        c_vk, _ = cap_q99(v_es, dlt_vk)
        cap_c1v = None if selp["cap"] == "none" else c_vk
        p3v_c1 = run_d3(v_es, pr_vk, cap_c1v, lin, True, delta=dlt_vk, rearm="below")
        h3v_c1 = float(calib_from_stat(v_es, p3v_c1.W)[5])
        rows.append({
            "seed": seed, "cap_k": c_k, "cap_v": c_v, "h1_0_k": h1k, "h1_0_v": h1v,
            "h3_5_c1_k": h3k_c1, "h3_5_c1_v": h3v_c1, "h3_5_q99type_k": h3k_q99, "h3_5_q99type_v": h3v_q99,
            "delta_k": {p: dk.get(p) for p in top}, "delta_v": {p: dv.get(p) for p in top}, "top": top,
        })
        lines.append(f"## seed {seed}")
        lines.append("")
        lines.append(f"- cap c (q99 on Δ+ kind): Kairos {c_k:.6g} · VELOX {c_v:.6g}")
        lines.append(f"- h1(0): Kairos {h1k:.6g} · VELOX {h1v:.6g}")
        lines.append(f"- h3(5) C1 `{c1_tag}`: Kairos {h3k_c1:.6g} · VELOX {h3v_c1:.6g}")
        lines.append(f"- h3(5) q99+type: Kairos {h3k_q99:.6g} · VELOX {h3v_q99:.6g}")
        lines.append("")
        lines.append("| program | δ_prog Kairos | δ_prog VELOX |")
        lines.append("| --- | ---: | ---: |")
        for p in top:
            ks = "" if dk.get(p) is None else dk[p]
            vs = "" if dv.get(p) is None else dv[p]
            lines.append(f"| {p} | {ks} | {vs} |")
        lines.append("")
    log = _log()
    path = assert_write_path(log / "SCALE_kairos_vs_velox.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    assert_write_path(log / "SCALE_kairos_vs_velox.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return path


def gt_sizes() -> list[dict]:
    gt = load_groundtruth(DATASET)
    es = load_stream(DATASET, 0, "test", gt.attacks[0].day)
    # need per-attack day
    out = []
    for a in gt.attacks:
        es = load_stream(DATASET, 0, "test", a.day)
        mi = mi_indices(es, a)
        out.append({"attack": a.name, "day": a.day, "P": len(a.P), "M": int(len(mi)), "G": len(a.G)})
    return out


def self_check(by: dict, csvp: Path, sel: dict) -> dict:
    evals = by[DATASET]
    e2, _, _ = earliness_of(evals, 2, "D4")
    c2 = earliness_from_csv(csvp, DATASET, 2, "D4")
    flags = []
    if abs(e2 - c2) > 1e-12:
        flags.append(f"earliness mismatch {e2} vs csv {c2}")
    # D1@b=0 h > val max
    for seed in SEEDS:
        v = load_val(seed)
        h0 = float(v["h1"]["0"])
        mx = float(v.get("val_max_proc_loss") or v.get("val_max_loss") or 0)
        if not (h0 > mx):
            flags.append(f"seed{seed} h1(0)={h0} not > val_max_proc={mx}")
        for b in BUDGETS:
            n = int(v.get("n_flagged_d1", {}).get(str(b), -1))
            if n != int(b):
                flags.append(f"seed{seed} D1 val flagged {n} != b={b}")
    sizes = gt_sizes()
    expect = {"Nginx_Backdoor_06": (2, 21), "Nginx_Backdoor_12": (24, 96), "Nginx_Backdoor_13": (14, 32)}
    for row in sizes:
        exp = expect.get(row["attack"])
        if exp and (row["P"], row["M"]) != exp:
            flags.append(f"GT {row['attack']} P/M={row['P']}/{row['M']} want {exp}")
    return {"ok": not flags, "flags": flags, "gt": sizes, "earliness_csv": c2, "earliness": e2}


def try_fidelity() -> dict:
    """D1@b=0 test-period process set vs PIDSMaker node_evaluation process nodes."""
    summary = Path(spec().summary)
    if not summary.is_file():
        return {
            "done": False,
            "reason": f"未做：公开数据包不含训练树 {summary.name}，无法对齐 node_evaluation",
        }
    if spec().name != "orthrus":
        try:
            import torch
            from firstalarm.kairos_paths import get_kairos_paths
            from firstalarm.paths import result_pth_path
        except Exception as e:  # noqa: BLE001
            return {"done": False, "reason": str(e)}
        rows = []
        for seed in SEEDS:
            rp = get_kairos_paths(seed)
            pth = result_pth_path(rp, 11)
            if not pth.is_file():
                return {"done": False, "reason": f"missing {pth}", "rows": rows}
            try:
                obj = torch.load(pth, map_location="cpu", weights_only=False)
            except TypeError:
                obj = torch.load(pth, map_location="cpu")
            info = {"seed": seed, "type": type(obj).__name__}
            if isinstance(obj, dict):
                info["keys"] = [str(k) for k in list(obj)[:30]]
            rows.append(info)
        return {
            "done": False,
            "reason": "未做：result_model_epoch_11.pth 不是与 D1@b=0 同口径的 process 集合，无法机械逐 seed 对齐",
            "sample": rows,
        }
    from firstalarm.alerts import alerted_procs_raw, crossings
    from firstalarm.config import TEST_DATES
    from firstalarm.kairos_align import load_kairos_stream
    from firstalarm.kairos_paths import get_scorer_paths
    from firstalarm.node_eval import _torch_load, load_indexid2msg, paper_type

    rows = []
    for seed in SEEDS:
        valj = load_val(seed)
        h0 = float(valj["h1"]["0"])
        d1 = set()
        for day in TEST_DATES[DATASET]:
            es = load_kairos_stream(seed, "test", day)
            d1 |= alerted_procs_raw(crossings(es, es.s.astype(float), h0, True))
        rp = get_scorer_paths(seed)
        sc_path = rp.evaluation / "precision_recall_dir" / "scores_model_epoch_11.pkl"
        if not sc_path.is_file():
            return {"done": False, "reason": f"missing {sc_path}", "rows": rows}
        sc = _torch_load(sc_path)
        msg = {}
        pkl = rp.construction / "indexid2msg" / "indexid2msg.pkl"
        if pkl.is_file():
            msg = load_indexid2msg(pkl)
        pm = set()
        n_pred = 0
        for nid, pred in zip(sc["nodes"], sc["y_preds"]):
            if int(pred) != 1:
                continue
            n_pred += 1
            typ = paper_type(msg.get(int(nid), ("unknown", ""))[0])
            if typ == "process":
                pm.add(int(nid))
        inter = d1 & pm
        rows.append({
            "seed": seed,
            "h1_0": h0,
            "n_d1_b0": len(d1),
            "n_pm_process": len(pm),
            "n_pm_pred": n_pred,
            "n_inter": len(inter),
            "n_only_d1": len(d1 - pm),
            "n_only_pm": len(pm - d1),
            "only_d1_sample": sorted(d1 - pm)[:20],
            "only_pm_sample": sorted(pm - d1)[:20],
            "inter_sample": sorted(inter)[:20],
        })
    return {
        "done": True,
        "reason": (
            "已做轻量对比：D1@b=0 为测试期 process 事件 loss≥h1(0) 的进程集合；"
            "PIDSMaker 为 node_evaluation 中 y_pred=1 且类型=process 的节点。"
            "两口径阈值不同（h1(0)=验证日最大 process loss 之上；PIDSMaker=max_val_loss），"
            "交集/差集如下，不作为判定输入。"
        ),
        "rows": rows,
    }


def nginx_two_lines(by: dict) -> list[dict]:
    """A1=Nginx_Backdoor_12, A2=Nginx_Backdoor_13, b=5: earliest P_i first_W_ge_h3 per seed, then first seed0 line."""
    evals = by[DATASET]
    out = []
    for name, tag in (("Nginx_Backdoor_12", "A1"), ("Nginx_Backdoor_13", "A2")):
        per_seed = []
        for ev in evals:
            att = ev["attacks"][name]
            rows = (ev.get("standing") or {}).get(name, {}).get("5", {})
            best = None
            for p in att["P"]:
                r = rows.get(str(p), {})
                first = r.get("first_W_ge_h3") or "none"
                rec = {
                    "seed": ev["seed"],
                    "proc": p,
                    "first_W_ge_h3": first,
                    "w_over_h_t0": r.get("w_over_h_t0"),
                    "n_alert_before_t0": r.get("n_alert_before_t0"),
                }
                if first != "none" and (best is None or first < best["first_W_ge_h3"]):
                    best = rec
            per_seed.append(best or {"seed": ev["seed"], "first_W_ge_h3": "none"})
        # report line: seed0 if present else first
        pick = next((r for r in per_seed if r.get("seed") == 0), per_seed[0])
        out.append({"attack": name, "label": tag, "day": evals[0]["attacks"][name]["day"], "pick": pick, "per_seed": per_seed})
    return out


def timing_rows(by: dict) -> list[dict]:
    rows = []
    for ev in by[DATASET]:
        t = ev.get("timing") or {}
        rows.append({
            "dataset": DATASET,
            "seed": ev["seed"],
            "cap": ev.get("cap"),
            "prior": ev.get("prior"),
            "rearm": ev.get("rearm"),
            "wall_s": t.get("wall_s"),
            "n_events": t.get("n_events"),
            "events_per_s": t.get("events_per_s"),
        })
    return rows


def _hits(evals: list[dict], b: int, rule: str) -> int:
    n = 0
    for ev in evals:
        for att in ev["attacks"].values():
            if att["rows"][str(b)][rule].get("hit"):
                n += 1
    return n


def protocol_sentence(v_c1: dict, k_d1: int, k_fa: int, signal: bool, pre_ok: bool) -> tuple[str, str]:
    """Return (category, fixed sentence). Sentence templates are frozen in PROTOCOL_v9."""
    if not pre_ok:
        return "pipeline failure", "论文不提 ORTHRUS。"
    x = f"{v_c1['E_FA_b5']:.4f}"
    y = f"{v_c1['E_D1_b5']:.4f}"
    f_fa = f"{v_c1['F_FA_b5']:.4f}"
    f_d1 = f"{v_c1['F_D1_b20']:.4f}"
    if v_c1["success"]:
        sent = (
            f"With ORTHRUS's per-event scores the gain holds: at $b=5$ FirstAlarm "
            f"reaches an earliness score of {x} against {y} for the event-level rule, "
            f"at $F=${f_fa} against {f_d1} at $b=20$."
        )
        return "gain", sent
    if signal:
        sent = (
            f"With ORTHRUS's per-event scores, which separate the attacks "
            f"(the event-level rule detects {k_d1} of the 15 pairs at $b=5$), "
            f"FirstAlarm adds no gain ({x} against {y}), so the gain is shown only with VELOX's scores."
        )
        return "no-gain-with-signal", sent
    sent = (
        f"With ORTHRUS's per-event scores the event-level rule detects {k_d1} of the 15 pairs "
        f"at $b=5$ and FirstAlarm {k_fa}, as with Kairos's."
    )
    return "no-gain-no-signal", sent


def write_results(sel: dict, by_c1: dict, by_q99: dict, csvp: Path, precheck: dict | None) -> Path:
    evs = by_c1[DATASET]
    chk = self_check(by_c1, csvp, sel)
    decomp = decompose(by_c1)
    v_c1 = verdict(evs)
    v_q99 = verdict(by_q99[DATASET])
    fid = try_fidelity()
    ngx = nginx_two_lines(by_c1)
    times = timing_rows(by_c1) + timing_rows(by_q99)
    log = _log()
    if precheck is None:
        pp = log / "PRECHECK.json"
        precheck = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else {"ok": None}
    if spec().name == "orthrus":
        return write_results_orthrus(sel, by_c1, by_q99, csvp, precheck, chk, decomp, v_c1, v_q99, fid, ngx, times)
    label = v_c1["label"]
    if precheck.get("ok") is False:
        label = "pipeline failure"
    lines = [
        "# RESULTS_v9_5_kairos",
        "",
        "scorer=Kairos epoch 11 edge_losses；rearm=reset；P1；预算 {0,1,2,5,10,20,50}；CADETS_E3 seed 0–4。THEIA 不跑。",
        "",
        "## 判定",
        "",
        f"- C1 选中组合：`{sel.get('cap')}_{sel.get('prior')}`（{sel.get('mark')}）。类别：**{label}**。",
        f"- 预注册：E_FA(b=5)−E_D1(b=5) ≥ 0.1 且 F_FA(b=5) ≤ F_D1(b=20)。C1：ΔE={v_c1['dE']:.4f}，F_FA={v_c1['F_FA_b5']:.4f}，F_D1@20={v_c1['F_D1_b20']:.4f} → {v_c1['label']}。",
        f"- q99+type：ΔE={v_q99['dE']:.4f}，F_FA={v_q99['F_FA_b5']:.4f}，F_D1@20={v_q99['F_D1_b20']:.4f} → {v_q99['label']}。",
        f"- 前置检查 ok={precheck.get('ok')}；自检 ok={chk['ok']}。",
        "",
        "## 前置检查",
        "",
        f"- seed 隔离：training 互异={((precheck.get('isolation') or {}).get('training_unique'))}；同名窗口两两 md5 冲突={((precheck.get('isolation') or {}).get('same_md5_pairs'))}。",
        f"- 10× 尺度标记（不剔除）：{precheck.get('scale_10x_seeds')}",
        "",
        "## 分解量 FA@b=5",
        "",
        f"- vs D1@b=5：{decomp['vs_d1_b5']}",
        f"- vs D1@b=20：{decomp['vs_d1_b20']}",
        "",
        "## nginx A1/A2（b=5，P_i 中最早越阈；已核实自 standing）",
        "",
    ]
    for row in ngx:
        p = row["pick"]
        lines.append(
            f"- {row['label']} {row['attack']} day={row['day']}: first={p.get('first_W_ge_h3')} "
            f"proc={p.get('proc')} W/h@t0={p.get('w_over_h_t0')} n_alert_before_t0={p.get('n_alert_before_t0')}"
        )
    lines += [
        "",
        "## 自检",
        "",
        f"- |P_i|/|M_i|：{chk['gt']}",
        f"- 期望 2/21、24/96、14/32。flags={chk['flags']}",
        f"- E from per_cell：table {chk['earliness']:.6f} csv {chk['earliness_csv']:.6f}",
        "",
        "## 保真度（可选）",
        "",
        f"- {fid.get('reason')}",
        "",
        "## 重放吞吐",
        "",
    ]
    for t in times:
        lines.append(
            f"- seed{t['seed']} {t['cap']}_{t['prior']} wall={t['wall_s']}s "
            f"n={t['n_events']} ev/s={t.get('events_per_s')}"
        )
    lines.append("")
    path = KAIROS_LOG / "RESULTS_v9_5_kairos.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (KAIROS_LOG / "RESULTS_v9_5_kairos.json").write_text(
        json.dumps(
            {
                "verdict_c1": v_c1,
                "verdict_q99_type": v_q99,
                "label": label,
                "selection": sel,
                "decompose": decomp,
                "self_check": chk,
                "fidelity": fid,
                "nginx": ngx,
                "timing": times,
                "precheck_ok": precheck.get("ok"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (KAIROS_ART / "timing.json").parent.mkdir(parents=True, exist_ok=True)
    (KAIROS_ART / "timing.json").write_text(json.dumps(times, indent=2, default=str), encoding="utf-8")
    return path


def write_results_orthrus(
    sel, by_c1, by_q99, csvp, precheck, chk, decomp, v_c1, v_q99, fid, ngx, times,
) -> Path:
    evs = by_c1[DATASET]
    log = _log()
    art = spec().art
    k_d1 = _hits(evs, 5, "D1")
    k_fa = _hits(evs, 5, "D4")
    signal = True  # v9-7 node_eval.json: seed 0/3/4, 3/5; do not re-judge
    # ok is False only when a precheck file says so. The public bundle has no
    # training-tree precheck, so a missing file must not replace the fixed sentence.
    pre_ok = precheck.get("ok") is not False
    category, sentence = protocol_sentence(v_c1, k_d1, k_fa, signal, pre_ok)
    q_cat, q_sent = protocol_sentence(v_q99, _hits(by_q99[DATASET], 5, "D1"), _hits(by_q99[DATASET], 5, "D4"), signal, pre_ok)
    label = category
    if precheck.get("ok") is False:
        label = "pipeline failure"
        sentence = "论文不提 ORTHRUS。"
    lines = [
        "# RESULTS_v9_8_orthrus",
        "",
        "scorer=ORTHRUS epoch 11 edge_losses；rearm=reset；P1；预算 {0,1,2,5,10,20,50}；CADETS_E3 seed 0–4。THEIA 不跑。",
        "信号判据引用 v9-7：seed 0/3/4 标记到 ≥1 个 GT 节点，3/5，signal 成立。本阶段不重新判定。",
        "",
        "## 判定",
        "",
        f"- C1 选中组合：`{sel.get('cap')}_{sel.get('prior')}`（{sel.get('mark')}）。类别：**{label}**。",
        f"- 预注册：E_FA(b=5)−E_D1(b=5) ≥ 0.1 且 F_FA(b=5) ≤ F_D1(b=20)。C1：ΔE={v_c1['dE']:.4f}，F_FA={v_c1['F_FA_b5']:.4f}，F_D1@20={v_c1['F_D1_b20']:.4f} → {v_c1['label']}。",
        f"- q99+type：ΔE={v_q99['dE']:.4f}，F_FA={v_q99['F_FA_b5']:.4f}，F_D1@20={v_q99['F_D1_b20']:.4f} → {v_q99['label']}。",
        f"- 固定句（C1）：{sentence}",
        f"- 固定句（q99+type 同一判定）：{q_sent}",
        f"- 前置检查 ok={precheck.get('ok')}；自检 ok={chk['ok']}。",
        f"- D1@b=5 hits={k_d1}/15；FA@b=5 hits={k_fa}/15。",
        f"- 自检 flags 不改判定：pipeline failure 仅当前置检查失败或重放出错。",
        "",
        "## 前置检查",
        "",
        f"- 预注册自 {precheck.get('prereg', {}).get('commit', '2913926')} 起 diff 空={((precheck.get('prereg') or {}).get('ok'))}。",
        f"- seed 隔离：training 互异={((precheck.get('isolation') or {}).get('training_unique'))}；同名窗口两两 md5 冲突={((precheck.get('isolation') or {}).get('same_md5_pairs'))}。",
        f"- 10× 尺度标记（不剔除）：{precheck.get('scale_10x_seeds')}",
        "",
        "## 分解量 FA@b=5",
        "",
        f"- vs D1@b=5：{decomp['vs_d1_b5']}",
        f"- vs D1@b=20：{decomp['vs_d1_b20']}",
        f"- vs D1@b=0：{decomp.get('vs_d1_b0')}",
        "",
        "## nginx A1/A2（b=5，P_i 中最早越阈；已核实自 standing）",
        "",
    ]
    for row in ngx:
        p = row["pick"]
        lines.append(
            f"- {row['label']} {row['attack']} day={row['day']}: first={p.get('first_W_ge_h3')} "
            f"proc={p.get('proc')} W/h@t0={p.get('w_over_h_t0')} n_alert_before_t0={p.get('n_alert_before_t0')}"
        )
        seeds_s = []
        for r in row.get("per_seed") or []:
            seeds_s.append(f"seed{r.get('seed')}={r.get('first_W_ge_h3')}")
        if seeds_s:
            lines.append(f"  per-seed: {', '.join(seeds_s)}")
    lines += [
        "",
        "## 自检",
        "",
        f"- |P_i|/|M_i|：{chk['gt']}",
        f"- 期望 2/21、24/96、14/32。flags={chk['flags']}",
        "- 验证日 flagged≠b：calib 用 nextafter(第 b+1 大 process max, +∞)；并列 max 时无法恰为 b（方法未改）。不改阈值、不改判定。",
        f"- E from per_cell：table {chk['earliness']:.6f} csv {chk['earliness_csv']:.6f}",
        "",
        "## D1 与 FA 全预算 (E, F)",
        "",
    ]
    for b in BUDGETS:
        e1, m1, _ = earliness_of(evs, int(b), "D1")
        e4, m4, _ = earliness_of(evs, int(b), "D4")
        lines.append(
            f"- b={b}: D1 E={e1:.4f} (miss {m1}) F={f_median(evs, int(b), 'D1'):.4f}；"
            f"FA E={e4:.4f} (miss {m4}) F={f_median(evs, int(b), 'D4'):.4f}"
        )
    lines += [
        "",
        "## 保真度（轻量）",
        "",
        f"- {fid.get('reason')}",
    ]
    for r in fid.get("rows") or []:
        lines.append(
            f"- seed{r.get('seed')}: |D1@b=0|={r.get('n_d1_b0')} |PM process|={r.get('n_pm_process')} "
            f"∩={r.get('n_inter')} only_D1={r.get('n_only_d1')} only_PM={r.get('n_only_pm')}"
        )
    lines += [
        "",
        "## 重放吞吐",
        "",
    ]
    for t in times:
        lines.append(
            f"- seed{t['seed']} {t['cap']}_{t['prior']} wall={t['wall_s']}s "
            f"n={t['n_events']} ev/s={t.get('events_per_s')}"
        )
    lines.append("")
    path = assert_write_path(log / "RESULTS_v9_8_orthrus.md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "verdict_c1": v_c1,
        "verdict_q99_type": v_q99,
        "label": label,
        "category": category,
        "sentence_c1": sentence,
        "sentence_q99_type": q_sent,
        "selection": sel,
        "decompose": decomp,
        "self_check": chk,
        "fidelity": fid,
        "nginx": ngx,
        "timing": times,
        "precheck_ok": precheck.get("ok"),
        "signal_cited": signal,
        "k_d1_b5": k_d1,
        "k_fa_b5": k_fa,
    }
    assert_write_path(log / "RESULTS_v9_8_orthrus.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    assert_write_path(art / "timing.json").write_text(json.dumps(times, indent=2, default=str), encoding="utf-8")
    return path

