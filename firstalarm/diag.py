"""DIAG_standing: per-process standing on attack days (from eval/val JSON)."""

from __future__ import annotations

from pathlib import Path

from firstalarm.config import ATTACK_DATES, LOG_ROOT, TABLE_BUDGETS, TEST_DATES, VAL_DATES, WATCH_PROG
from firstalarm.pipeline import load_eval, load_val


def write_standing(tag: str, rearm: str, cap_by_ds: dict, datasets, seeds) -> Path:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    lines = [f"# DIAG_standing_{tag}", "", f"rearm={rearm} cap_by_ds={cap_by_ds}", ""]
    for ds in datasets:
        cap, prior = cap_by_ds[ds]
        watch = WATCH_PROG[ds]
        lines.append(f"## {ds}")
        lines.append("")
        for seed in seeds:
            ev = load_eval(ds, seed, rearm, cap, prior)
            valj = load_val(ds, seed)
            for name, att in ev["attacks"].items():
                for b in TABLE_BUDGETS:
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
                        lo = r.get("W_min")
                        hi = r.get("W_max")
                        lo_s = "" if lo is None else f"{float(lo):.4g}"
                        hi_s = "" if hi is None else f"{float(hi):.4g}"
                        lines.append(
                            f"| {p} | {r.get('first_W_ge_h3', '')} | {rs} | "
                            f"{r.get('n_alert_before_t0', '')} | {r.get('first_in_window', '')} | {lo_s} | {hi_s} |"
                        )
                    lines.append("")

            lines.append(f"### watch {watch} val/non-attack seed{seed}")
            lines.append("")
            lines.append("| seed | split | day | b | n_proc_kind | n_flagged |")
            lines.append("| ---: | --- | --- | ---: | ---: | ---: |")
            pair = valj["pairs"][f"{cap}_{prior}"]
            vw = pair.get("watch") or {}
            for b in TABLE_BUDGETS:
                row = vw.get(str(b), {})
                lines.append(
                    f"| {seed} | val | {VAL_DATES[ds]} | {b} | {row.get('n_proc_kind', '')} | {row.get('n_flagged', '')} |"
                )
            non_att = [d for d in TEST_DATES[ds] if d not in ATTACK_DATES[ds]]
            tw = ev.get("watch") or {}
            for day in non_att:
                for b in TABLE_BUDGETS:
                    row = (tw.get(day) or {}).get(str(b), {})
                    lines.append(
                        f"| {seed} | test | {day} | {b} | {row.get('n_proc_kind', '')} | {row.get('n_flagged', '')} |"
                    )
            lines.append("")

    path = LOG_ROOT / f"DIAG_standing_{tag}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
