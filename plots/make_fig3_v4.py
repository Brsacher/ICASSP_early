#!/usr/bin/env python3
"""Fig. 3: earliness score E against benign processes flagged per test day F (CADETS), v4.

Usage
  python plots/make_fig3_v4.py results/figA_reset_CADETS_E3.json
  python make_fig3_v4.py <json> --linear     # linear x axis instead of log (for comparison)

Writes fig3_frontier_v4.pdf and fig3_frontier_v4.png next to this script and prints the
21 plotted points so they can be checked against Table 1 / v9-12.

Changes against v3:
  - no in-figure title, no "CADETS E3" text anywhere
  - axis label "Earliness score"; legend entry "FirstAlarm (Ours)"
  - legend in the upper left, order D1, D3, Ours (same order as Table 1)
  - log x axis runs 0.2 .. 100 so the major ticks are 10^0, 10^1, 10^2
Fonts: Times New Roman if installed, else Liberation Serif / Nimbus Roman / DejaVu Serif;
embedded as TrueType (pdf.fonttype 42), never Type 3.
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, NullFormatter

matplotlib.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Liberation Serif", "Nimbus Roman", "Nimbus Roman No9 L",
                   "TeX Gyre Termes", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 7.5, "axes.linewidth": 0.6,
})

BUDGETS = [0, 1, 2, 5, 10, 20, 50]
RULES = {"D1": "D1", "D3": "D3", "FA": "FA", "D4": "FA", "FirstAlarm": "FA"}
E_KEYS = ["E", "e", "earliness", "earliness_score", "score"]
F_KEYS = ["F", "f", "F_median", "f_median", "fp", "mean_B_median", "mean_B"]
# points left unlabelled to avoid clutter (the caption lists the budget grid)
SKIP = {("D1", 10)}
# detected pairs at the two points joined by the dotted line (v9-6)
DETECTED = {("FA", 5): "14/15", ("D1", 20): "10/15"}

STYLE = {  # plotting order is D3, D1, FA (FA on top); legend order is D1, D3, FA
    "D1": dict(color="#7f7f7f", ls="-", marker="o", ms=3.8, lw=1.1, label="detector's own rule (D1)"),
    "D3": dict(color="#7fb2d9", ls="--", marker="^", ms=4.2, lw=1.1, label="memory channel (D3)"),
    "FA": dict(color="#1f4e79", ls="-", marker="s", ms=4.2, lw=1.3, label="FirstAlarm (Ours)"),
}
LEGEND_ORDER = ["D1", "D3", "FA"]

# budget-label offsets in points (dx, dy) and alignment; per-point overrides
OFFSET = {"FA": (-3, 5, "right", "bottom"), "D1": (3, -4, "left", "top"), "D3": (3, -4, "left", "top")}
OVERRIDE = {("D1", 0): (0, 5, "center", "bottom"), ("D1", 1): (-2, -4, "right", "top"),
            ("D1", 2): (3, -4, "left", "top"),
            ("D3", 0): (-1, 5, "center", "bottom"), ("D3", 1): (0, 5, "center", "bottom"),
            ("D3", 2): (2, -5, "center", "top"), ("FA", 0): (0, 5, "center", "bottom"),
            ("FA", 1): (0, 5, "center", "bottom"), ("FA", 2): (0, 5, "center", "bottom"),
            ("FA", 50): (-6, 0, "right", "center")}


def _pick(d, keys, what):
    for k in keys:
        if k in d:
            return float(d[k])
    raise SystemExit(f"cannot find {what} among keys {list(d)}; edit E_KEYS / F_KEYS")


def load(path):
    data = {"D1": {}, "D3": {}, "FA": {}}
    raw = json.load(open(path))
    for b, rules in raw.items():
        if not str(b).lstrip("-").isdigit():
            continue
        for rname, rec in rules.items():
            if rname in RULES and isinstance(rec, dict):
                data[RULES[rname]][int(b)] = (_pick(rec, F_KEYS, "F"), _pick(rec, E_KEYS, "E"))
    for r in data:
        missing = [b for b in BUDGETS if b not in data[r]]
        if missing:
            raise SystemExit(f"{r}: no data for budgets {missing}")
    return data


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    linear = "--linear" in sys.argv[2:]
    data = load(sys.argv[1])

    fig, ax = plt.subplots(figsize=(3.39, 1.95))
    for r in ("D3", "D1", "FA"):
        xs = [data[r][b][0] for b in BUDGETS]
        ys = [data[r][b][1] for b in BUDGETS]
        ax.plot(xs, ys, zorder=3 if r == "FA" else 2, **STYLE[r])

    # dotted connector: detector's rule at b=20 and FirstAlarm at b=5 (about the same F)
    (x1, y1), (x2, y2) = data["D1"][20], data["FA"][5]
    ax.plot([x1, x2], [y1, y2], ls=":", color="#c0392b", lw=1.1, zorder=1)

    for r in ("D1", "D3", "FA"):
        for b in BUDGETS:
            x, y = data[r][b]
            if (r, b) in SKIP:
                continue
            if r == "D3":                          # label a D3 point only where its F differs from FirstAlarm's
                xf = data["FA"][b][0]
                if abs(x - xf) <= 0.03 * max(x, xf):
                    continue
            dx, dy, ha, va = OVERRIDE.get((r, b), OFFSET[r])
            txt, weight = str(b), "normal"
            if (r, b) in DETECTED:
                txt, weight = f"{b} ({DETECTED[(r, b)]})", "bold"
            ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va,
                        fontsize=6.5, color=STYLE[r]["color"], fontweight=weight, zorder=4)

    if linear:
        ax.set_xlim(0, 70)
        ax.set_xticks([0, 10, 20, 30, 40, 50, 60, 70])
    else:
        ax.set_xscale("log")
        ax.set_xlim(0.2, 100)                      # major ticks 10^0, 10^1, 10^2
        ax.xaxis.set_major_locator(LogLocator(base=10, numticks=4))
        ax.xaxis.set_minor_locator(LogLocator(base=10, subs=(2, 3, 5), numticks=12))
        ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel(r"$F$, benign processes flagged per test day", labelpad=2)
    ax.set_ylabel("Earliness score", labelpad=2)
    ax.grid(True, which="major", lw=0.4, color="#dddddd")
    ax.tick_params(length=2.5, width=0.5, pad=2)
    ax.tick_params(which="minor", length=1.5, width=0.4)
    handles, labels = ax.get_legend_handles_labels()
    order = [labels.index(STYLE[k]["label"]) for k in LEGEND_ORDER]
    ax.legend([handles[i] for i in order], [labels[i] for i in order], loc="upper left",
              fontsize=6.5, frameon=False, handlelength=2.4, borderaxespad=0.3, labelspacing=0.25)
    fig.subplots_adjust(left=0.125, right=0.965, top=0.975, bottom=0.2)
    stem = "fig3_frontier_v4" + ("_linear" if linear else "")
    fig.savefig(stem + ".pdf", metadata={"Creator": None, "Producer": None})
    fig.savefig(stem + ".png", dpi=400)

    print(f"{'rule':4s} {'b':>3s} {'F':>8s} {'E':>8s}")
    for r in ("D1", "D3", "FA"):
        for b in BUDGETS:
            print(f"{r:4s} {b:3d} {data[r][b][0]:8.3f} {data[r][b][1]:8.4f}")
    print("check against Table 1 / v9-12: FA b=5 -> F 12.0, E 0.7280; D1 b=20 -> F 15, E 0.545; "
          "D1 b=5 -> F 5.0, E 0.4828")
    print(f"wrote {stem}.pdf / .png")


if __name__ == "__main__":
    main()
