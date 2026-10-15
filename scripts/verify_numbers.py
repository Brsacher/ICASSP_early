#!/usr/bin/env python3
"""Assert the shipped result files against paper_numbers.md (v2).

Tolerance on raw source values is 1e-3. Rows marked 论文有误 or 口径不同
are checked against the repository values, not the printed sentence.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
TOL = 1e-3

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"OK  {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"FAIL {name}: {detail}")


def close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def load_csv():
    rows = []
    with (RES / "per_cell_reset.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["seed"] = int(r["seed"])
            r["b"] = int(r["b"])
            r["hit"] = r["hit"] == "1"
            r["rho"] = float(r["rho"]) if r["rho"] else None
            r["delay"] = float(r["delay"]) if r["delay"] else None
            r["fp_day"] = float(r["fp_day"]) if r["fp_day"] else None
            rows.append(r)
    return rows


def subset(rows, ds, attack, b, rule):
    return [r for r in rows if r["dataset"] == ds and r["attack"] == attack and r["b"] == b and r["rule"] == rule]


def med(xs):
    return float(statistics.median(xs))


def fmt_rho(x):
    return f"{float(x):.2f}"


def fmt_d(x):
    return int(round(float(x)))


ROWS = load_csv()
FIG = json.loads((RES / "figA_reset_CADETS_E3.json").read_text(encoding="utf-8"))
DEC = json.loads((RES / "DECOMP_v9_6.json").read_text(encoding="utf-8"))
GT = {
    "CADETS_E3": json.loads((RES / "groundtruth_CADETS_E3.json").read_text(encoding="utf-8")),
    "THEIA_E3": json.loads((RES / "groundtruth_THEIA_E3.json").read_text(encoding="utf-8")),
}
SEL = {
    "CADETS_E3": json.loads((RES / "selection_CADETS_E3.json").read_text(encoding="utf-8")),
    "THEIA_E3": json.loads((RES / "selection_THEIA_E3.json").read_text(encoding="utf-8")),
}


def attack_cell(ds, name):
    for a in GT[ds]["attacks"]:
        if a["name"] == name:
            return a
    raise KeyError(name)


def assert_table(code, ds, attack, b, rule, rho_s, k, d_s):
    rows = subset(ROWS, ds, attack, b, rule)
    hits = [r for r in rows if r["hit"]]
    rho = med([r["rho"] for r in hits]) if hits else None
    delay = med([r["delay"] for r in hits]) if hits else None
    ok = len(hits) == k and (hits and fmt_rho(rho) == rho_s and fmt_d(delay) == d_s)
    detail = f"k={len(hits)} rho={None if rho is None else fmt_rho(rho)} d={None if delay is None else fmt_d(delay)} raw_rho={rho} raw_d={delay}"
    check(code + f" {rule}", ok, detail)


# --- T1-T5 from per_cell (Ours = D4) ---
SPECS = [
    ("T1", "CADETS_E3", "Nginx_Backdoor_06", [("D1", "0.24", 2, 271), ("D3", "0.29", 5, 174), ("D4", "0.29", 5, 174)]),
    ("T2", "CADETS_E3", "Nginx_Backdoor_12", [("D1", "0.28", 4, 254), ("D3", "0.10", 4, 83), ("D4", "0.12", 5, 83)]),
    ("T3", "CADETS_E3", "Nginx_Backdoor_13", [("D1", "0.06", 3, 111), ("D3", "0.34", 3, 251), ("D4", "0.20", 4, 181)]),
    ("T4", "THEIA_E3", "Firefox_Backdoor_Drakon_In_Memory", [("D1", "0.31", 1, 330), ("D3", "0.00", 1, 32), ("D4", "0.16", 2, 181)]),
    ("T5", "THEIA_E3", "Browser_Extension_Drakon_Dropper", [("D1", "0.01", 4, 2), ("D3", "0.44", 4, 619), ("D4", "0.22", 4, 311)]),
]
for code, ds, attack, cols in SPECS:
    for rule, rho_s, k, d_s in cols:
        assert_table(code, ds, attack, 5, rule, rho_s, k, d_s)

# --- Fig. 3, 21 points. Paper prints four decimals; source is the JSON. ---
FIG_PAPER = {
    0: {"D1": (0.25, 0.3852), "D3": (0.50, 0.0476), "D4": (1.00, 0.4328)},
    1: {"D1": (1.00, 0.4203), "D3": (2.25, 0.1770), "D4": (2.50, 0.4664)},
    2: {"D1": (1.25, 0.4203), "D3": (3.25, 0.1612), "D4": (4.25, 0.4699)},
    5: {"D1": (5.00, 0.4828), "D3": (12.00, 0.5969), "D4": (12.00, 0.7280)},
    10: {"D1": (6.75, 0.5453), "D3": (22.75, 0.6455), "D4": (22.75, 0.7671)},
    20: {"D1": (15.00, 0.5453), "D3": (34.50, 0.6986), "D4": (34.50, 0.8188)},
    50: {"D1": (41.00, 0.6513), "D3": (65.50, 0.8708), "D4": (66.25, 0.9292)},
}
for b, rules in FIG_PAPER.items():
    for rule, (f_p, e_p) in rules.items():
        rec = FIG[str(b)][rule]
        ok = close(rec["F_median"], f_p) and close(rec["earliness"], e_p)
        check(f"Fig.3 b={b} {rule}", ok, f"file F={rec['F_median']} E={rec['earliness']}")

# --- T6-T9 from the same JSON / table source values ---
b5 = FIG["5"]
check("T6 D1 E", close(b5["D1"]["earliness"], 0.4828) and b5["D1"]["n_miss"] == 6, str(b5["D1"]))
check("T6 D3 E", close(b5["D3"]["earliness"], 0.5969) and b5["D3"]["n_miss"] == 3, str(b5["D3"]))
check("T6 D4 E", close(b5["D4"]["earliness"], 0.7280) and b5["D4"]["n_miss"] == 1, str(b5["D4"]))
check("T8", close(b5["D1"]["F_median"], 5) and close(b5["D3"]["F_median"], 12) and close(b5["D4"]["F_median"], 12))

# THEIA bottom bar is in TABLE1_reset.md (b=5 column).
table = (RES / "TABLE1_reset.md").read_text(encoding="utf-8")
for label, token in (
    ("T7 D1", "| THEIA_E3 | earliness D1 (n_miss) | 0.4246 (5) | 0.4246 (5) |"),
    ("T7 D3", "| THEIA_E3 | earliness D3 (n_miss) | 0.2705 (5) | 0.2705 (5) |"),
    ("T7 D4", "| THEIA_E3 | earliness D4 (n_miss) | 0.4252 (4) | 0.4252 (4) |"),
    ("T9 D1", "| THEIA_E3 | F D1 | 5.0000 | 10.6667 |"),
    ("T9 D3", "| THEIA_E3 | F D3 | 16.3333 | 16.3333 |"),
    ("T9 D4", "| THEIA_E3 | F D4 | 20.0000 | 20.0000 |"),
):
    check(label, token in table, "row missing from TABLE1_reset.md")

# --- A1-A4 ---
fa5 = DEC["A"]["CADETS_E3"]["FA@5_vs_D1@5"]
fa20 = DEC["A"]["CADETS_E3"]["FA@5_vs_D1@20"]
fa0 = DEC["A"]["CADETS_E3"]["FA@5_vs_D1@0"]
check("A1", fa5["n_both"] + fa5["n_fa_only"] == 14 and fa5["n_both"] + fa5["n_d1_only"] == 9,
      f"{fa5['n_both']} {fa5['n_fa_only']} {fa5['n_d1_only']}")
# Paper prints 25%. Source mean is 0.2537 (Q1-4 / A2).
check("A2", close(fa0["fa_only"]["mean_rho"], 0.2537202380952381), str(fa0["fa_only"]))
check("A3", close(1 - b5["D4"]["earliness"], 0.2720) and close(1 - b5["D1"]["earliness"], 0.5172))
check("A4", fa20["n_both"] + fa20["n_d1_only"] == 10, str(fa20["n_both"] + fa20["n_d1_only"]))

# --- D2-D6 |P| from groundtruth.json. |M| is not stored; it is n_seen/rho on any hit. ---
MI = {
    ("CADETS_E3", "Nginx_Backdoor_06"): (2, 21),
    ("CADETS_E3", "Nginx_Backdoor_12"): (24, 96),
    ("CADETS_E3", "Nginx_Backdoor_13"): (14, 32),
    ("THEIA_E3", "Firefox_Backdoor_Drakon_In_Memory"): (47, 173),
    ("THEIA_E3", "Browser_Extension_Drakon_Dropper"): (49, 156),
}
for code, key in zip(("D2", "D3", "D4", "D5", "D6"), MI):
    ds, name = key
    want_p, want_m = MI[key]
    got_p = len(attack_cell(ds, name)["P"])
    # |M| is not a field of groundtruth.json. It is the smallest integer such
    # that every detected rho at b=5 is an integer count over |M|.
    cands = []
    for m in range(1, 400):
        good = True
        used = False
        for r in subset(ROWS, ds, name, 5, "D4"):
            if r["hit"] and r["rho"] and r["rho"] > 0:
                used = True
                if abs(r["rho"] * m - round(r["rho"] * m)) > 1e-6:
                    good = False
                    break
        if used and good:
            cands.append(m)
    got_m = min(cands) if cands else None
    check(code, got_p == want_p and got_m == want_m, f"P={got_p} M={got_m}")

# D7 论文有误: A5 seed 0 D1@b=0 is event 148, not within the first two.
# Paper: "on the seeds where it detects them, alerts within their first two malicious events".
a5 = subset(ROWS, "THEIA_E3", "Browser_Extension_Drakon_Dropper", 0, "D1")
a3 = subset(ROWS, "CADETS_E3", "Nginx_Backdoor_13", 0, "D1")
def n_seen(r, m):
    return None if not r["hit"] else int(round(r["rho"] * m))
a5_ns = {r["seed"]: n_seen(r, 156) for r in a5}
a3_ns = {r["seed"]: n_seen(r, 32) for r in a3}
check("D7 A3 seeds", a3_ns[1] == 2 and a3_ns[3] == 2, str(a3_ns))
check("D7 A5 seed0", a5_ns[0] == 148 and a5_ns[3] == 1 and a5_ns[4] == 1, str(a5_ns))

# D8
for b, diff in ((0, 0.047619), (1, 0.046032), (2, 0.049603)):
    e_fa = FIG[str(b)]["D4"]["earliness"]
    e_d1 = FIG[str(b)]["D1"]["earliness"]
    check(f"D8 b={b}", close(e_fa - e_d1, diff), f"{e_fa - e_d1}")

# D9
step = {s["step"]: s for s in DEC["B"]["steps"]}
check("D9", step["D2→D3"]["n_changed"] == 2, str(step["D2→D3"]["n_changed"]))

# D10
check("D10", SEL["CADETS_E3"]["cap"] == "q99" and SEL["CADETS_E3"]["prior"] == "type"
      and SEL["THEIA_E3"]["cap"] == "q99" and SEL["THEIA_E3"]["prior"] == "kind"
      and SEL["CADETS_E3"]["pairs"]["q99_type"]["n_pass"] == 4
      and SEL["THEIA_E3"]["pairs"]["q99_kind"]["n_pass"] == 5)

# Q1
check("Q1-1", close(b5["D1"]["earliness"], 0.482837) and close(b5["D4"]["earliness"], 0.727976))
check("Q1-2", close(FIG["20"]["D1"]["F_median"], 15) and close(FIG["5"]["D4"]["F_median"], 12)
      and fa20["n_both"] + fa20["n_d1_only"] == 10)
check("Q1-3", fa0["both_timing"]["FA_earlier"] == 4 and fa0["both_timing"]["same"] == 4
      and fa0["both_timing"]["FA_later"] == 0 and fa0["n_fa_only"] == 6, str(fa0["both_timing"]))
check("Q1-4", close(fa0["fa_only"]["mean_rho"], 0.2537202380952381) and close(fa0["fa_only"]["mean_d"], 261.075665415))
# Q1-5 论文有误: paper says 0.20 against 0.21. Repository means are 0.19475 / 0.21187.
check("Q1-5", close(fa5["rho_both"]["FA"]["mean"], 0.19475446428571427)
      and close(fa5["rho_both"]["D1"]["mean"], 0.21186755952380953),
      str(fa5["rho_both"]))

def delays(ds, attack, b, rule):
    return [r["delay"] for r in subset(ROWS, ds, attack, b, rule)]

def nseens(ds, attack, b, rule, m):
    return [n_seen(r, m) for r in subset(ROWS, ds, attack, b, rule)]

# Q1-6 口径不同: paper says (0.12, 83 s) on all five seeds.
# Four seeds are near 83 s; seed 3 is 984.15 s (event 38). The printed pair is the median.
a2_d = delays("CADETS_E3", "Nginx_Backdoor_12", 5, "D4")
a2_n = nseens("CADETS_E3", "Nginx_Backdoor_12", 5, "D4", 96)
check("Q1-6", a2_n == [12, 7, 12, 38, 7] and close(med(a2_d), 83.166196193) and close(max(a2_d), 984.146170955),
      f"n={a2_n} d={a2_d}")
a2_d1_n = nseens("CADETS_E3", "Nginx_Backdoor_12", 5, "D1", 96)
a2_d1_d = [r["delay"] for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_12", 5, "D1") if r["hit"]]
check("Q1-7", a2_d1_n == [27, 27, 27, 27, None] and all(close(x, 254.10618644) for x in a2_d1_d), str(a2_d1_n))
a1_n = nseens("CADETS_E3", "Nginx_Backdoor_06", 5, "D4", 21)
a1_d = delays("CADETS_E3", "Nginx_Backdoor_06", 5, "D4")
a1_d1 = nseens("CADETS_E3", "Nginx_Backdoor_06", 5, "D1", 21)
check("Q1-8", a1_n == [1, 6, 12, 9, 3] and med(a1_n) == 6 and a1_d1 == [None, 9, None, 1, None]
      and close(med(a1_d), 173.596169278), f"n={a1_n} d={a1_d} d1={a1_d1}")
# Q1-9 write is event 10 of m0_events.csv (1-based data row 10).
m0 = (ROOT / "plots/m0_events.csv").read_text(encoding="utf-8").splitlines()[1:]
write = [ln for ln in m0 if ",WRITE,/tmp/vUgefal," in ln][0]
write_ns = int(write.split(",")[0])
t0 = attack_cell("CADETS_E3", "Nginx_Backdoor_06")["t0"]
write_s = (write_ns - t0) / 1e9
check("Q1-9", close(write_s, 709.886158284) and write_s > med(a1_d), str(write_s))
check("Q1-10", sum(r["hit"] for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_13", 5, "D4")) == 4
      and sum(r["hit"] for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_13", 5, "D1")) == 3)

# Q2
ladder = [step[k]["E_after"] for k in ("∅→D1", "D1→D2", "D2→D3", "D3→D4")]
check("Q2-1", all(close(a, b) for a, b in zip(ladder, (0.4828373, 0.5874008, 0.5969246, 0.7279762))), str(ladder))
# Q2-2 论文有误: paper says the tenth event on four seeds. Events are 12, 7, 12, 7.
d2_n = [n for n in nseens("CADETS_E3", "Nginx_Backdoor_12", 5, "D2", 96) if n is not None]
check("Q2-2", d2_n == [12, 7, 12, 7] and 10 not in d2_n, str(d2_n))
# Q2-3 口径不同: net +2 = three new seeds minus one lost seed. Paper says "two more seeds".
d1_hits = {r["seed"] for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_06", 5, "D1") if r["hit"]}
d2_hits = {r["seed"] for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_06", 5, "D2") if r["hit"]}
check("Q2-3", d1_hits == {1, 3} and d2_hits == {0, 1, 2, 4}, f"{d1_hits} -> {d2_hits}")
check("Q2-4", fmt_rho(med([r["rho"] for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_13", 5, "D2") if r["hit"]])) == "0.34")
ch = {(c["attack"], c["seed"]): c for c in step["D2→D3"]["changed"]}
check("Q2-5", set(ch) == {("Nginx_Backdoor_06", 2), ("Nginx_Backdoor_06", 3)}
      and close(ch[("Nginx_Backdoor_06", 2)]["rho_before"], 0.2857142857142857)
      and close(ch[("Nginx_Backdoor_06", 2)]["rho_after"], 0.5714285714285714)
      and ch[("Nginx_Backdoor_06", 3)]["rho_before"] is None
      and close(ch[("Nginx_Backdoor_06", 3)]["rho_after"], 0.5714285714285714))
csec = DEC["C"]
check("Q2-6", csec["n"] == 37 and csec["by_channel"]["D3"] == 20 and csec["n_chain_M"] == 34 and csec["n_cross"] == 7,
      str({k: csec[k] for k in ("n", "n_chain_M", "n_cross")}) + str(csec["by_channel"]))
ch4 = step["D3→D4"]["changed"]
check("Q2-7", ch4 and len(ch4) == 4 and close(b5["D3"]["F_median"], 12) and close(b5["D4"]["F_median"], 12),
      str([(c["attack"], c["seed"]) for c in ch4]))

# Q3
check("Q3-1", close(FIG["0"]["D1"]["F_median"], 0.25) and close(FIG["50"]["D1"]["F_median"], 41)
      and close(FIG["0"]["D1"]["earliness"], 0.3852) and close(FIG["50"]["D1"]["earliness"], 0.6513))
check("Q3-2", close(b5["D4"]["earliness"], 0.7280) and close(FIG["20"]["D1"]["earliness"], 0.5453))
check("Q3-3", FIG["10"]["D4"]["n_miss"] == 0 and FIG["20"]["D4"]["n_miss"] == 0 and FIG["50"]["D4"]["n_miss"] == 0)
check("Q3-4", close(b5["D3"]["F_median"], 12) and close(b5["D1"]["F_median"], 5))
# Q3-5 attack-day 04-12, 83 s windows, max < 0.01
p83 = []
for rec in DEC["D"]["attack_days"]:
    if rec["day"] == "2018-04-12":
        p83.append(rec["p_placebo"]["83.0"]["p"])
check("Q3-5", p83 and max(p83) < 0.01 and close(max(p83), 0.00900473933649289), str(p83))
pL = [rec["p_placebo"][str(rec["d_cell"])]["p"] for rec in DEC["D"]["attack_days"] if rec["day"] == "2018-04-06"]
check("Q3-6", close(min(a1_d), 12.096172059) and close(max(a1_d), 796.536154997) and close(max(pL), 0.1592920353982301),
      f"d={a1_d} p={pL}")
# F' from the markdown line
check("Q3-7", "| CADETS_E3 | 5 | D3 | 12.0000 | 12.5000 |" in (RES / "DECOMP_v9_6.md").read_text(encoding="utf-8")
      or "| CADETS_E3 | 5 | FA | 12.0000 | 12.5000 |" in (RES / "DECOMP_v9_6.md").read_text(encoding="utf-8"))
npre = [rec["n_alert_before_t0"] for rec in DEC["D"]["attack_days"]]
check("Q3-8", npre == [1, 1, 4, 2, 9, 5, 3, 1, 5, 2], str(npre))

# S
kind = (RES / "TABLE1_reset_q99_kind.md").read_text(encoding="utf-8")
check("S1", "| CADETS_E3 | earliness D4 (n_miss) | 0.3852 (6) | 0.5869 (2) |" in kind
      and "| CADETS_E3 | F D4 | 3.5000 | 7.0000 |" in kind)
check("S2", "| THEIA_E3 | earliness D4 (n_miss) | 0.4252 (4) | 0.4252 (4) |" in table
      and "| THEIA_E3 | earliness D1 (n_miss) | 0.4246 (5) | 0.4246 (5) |" in table)
check("S3", "| THEIA_E3 | F D4 | 20.0000 | 20.0000 |" in table and "| THEIA_E3 | F D1 | 5.0000 | 10.6667 |" in table)
theia = (RES / "THEIA_diag.md").read_text(encoding="utf-8")
check("S4", all(tok in theia for tok in ("2.000", "7.000", "1.796", "firefox", "fluxbox")))
s2 = [r for r in subset(ROWS, "THEIA_E3", "Firefox_Backdoor_Drakon_In_Memory", 5, "D4") if r["seed"] == 2][0]
check("S5", s2["hit"] and close(s2["delay"], 31.824950275) and s2["rho"] == 0.0 and s2["chain_has_M"] == "0"
      and s2["trig"] == "nM" and s2["channel"] == "D3", str(s2))

# X
orth = (RES / "RESULTS_v9_8_orthrus.md").read_text(encoding="utf-8")
kai = (RES / "RESULTS_v9_5_kairos.md").read_text(encoding="utf-8")
check("X1", "0.0820 against 0.1682" in orth and "5 of the 15" in orth)
check("X2", "'d1_only': 2" in kai or '"d1_only": 2' in kai or "d1_only': 2" in kai)
persist = (RES / "PERSIST_three_scorers.md").read_text(encoding="utf-8")
check("X3", "| frac_pos      | 0.4286   | 0.4003   | 0.2500    | 0.2434    | 0.3333     | 0.2559     |" in persist)


# C1-C9: protocol constants in the code, not printed floats. Read as text so this
# script stays on the standard library.
src_cfg = (ROOT / "firstalarm/config.py").read_text(encoding="utf-8")
src_table = (ROOT / "firstalarm/table1.py").read_text(encoding="utf-8")
src_rent = (ROOT / "firstalarm/rent.py").read_text(encoding="utf-8")
src_rules = (ROOT / "firstalarm/rules.py").read_text(encoding="utf-8")
check("C1", "PRE_T0_NS = 60 * 10**9" in src_cfg)
check("C2", "float(np.median(" in src_table)
check("C3", "N_MIN_KIND = 100" in src_cfg and "np.quantile(xs, 0.75" in src_rent)
check("C4", "WARMUP = 5" in src_cfg)
check("C5", "np.quantile(pos, 0.99" in src_rent and "x > 0.0" in src_rent)
# creation key (parent program, child program); handover key adds object type
check("C6", "pk = (kinds.get(p, \"unknown\"), kinds.get(c, \"unknown\"))" in src_rules
      and "pat_h: dict[tuple[str, str, int], int]" in src_rules)
check("C7", "np.nextafter(xs[b], np.inf)" in (ROOT / "firstalarm/calibrate.py").read_text(encoding="utf-8"))
check("C8", "C1_LO = 0.5" in src_cfg and "C1_HI = 2.0" in src_cfg
      and SEL["CADETS_E3"]["pairs"]["q99_type"]["n_pass"] == 4
      and SEL["THEIA_E3"]["pairs"]["q99_kind"]["n_pass"] == 5)
check("C9", "BUDGETS = (0, 1, 2, 5, 10, 20, 50)" in src_cfg)

# F1: CADETS 6 April, seed 1, D1 at b=0. |M| is not a JSON field; 9/21 on this cell fixes it at 21.
a1gt = attack_cell("CADETS_E3", "Nginx_Backdoor_06")
f1 = [r for r in subset(ROWS, "CADETS_E3", "Nginx_Backdoor_06", 0, "D1") if r["seed"] == 1][0]
check("F1-1", a1gt["t0"] == 1523028000000000000 and a1gt["t1"] == 1523030940000000000
      and a1gt["t1"] - a1gt["t0"] == 2940 * 10**9)
check("F1-2", len(a1gt["P"]) == 2 and f1["hit"] and abs(f1["rho"] * 21 - 9) < 1e-6, str(f1["rho"]))
check("F1-3", f1["hit"] and close(f1["rho"], 9 / 21) and close(f1["delay"], 528.956163948)
      and int(round(f1["rho"] * 21)) == 9, str(f1))

# T6 / T7 detected-pair counts. Fig. 3 stores n and n_miss; Table 1 stores n_miss.
check("T6 counts", FIG["5"]["D1"]["n"] - FIG["5"]["D1"]["n_miss"] == 9
      and FIG["5"]["D3"]["n"] - FIG["5"]["D3"]["n_miss"] == 12
      and FIG["5"]["D4"]["n"] - FIG["5"]["D4"]["n_miss"] == 14,
      str({r: (FIG["5"][r]["n"], FIG["5"][r]["n_miss"]) for r in ("D1", "D3", "D4")}))


def _miss_b5(ds: str, rule: str):
    import re
    for line in table.splitlines():
        if f"| {ds} | earliness {rule} " in line:
            return int(re.findall(r"\((\d+)\)", line)[-1])
    return None


check("T7 counts", _miss_b5("THEIA_E3", "D1") == 5 and _miss_b5("THEIA_E3", "D3") == 5
      and _miss_b5("THEIA_E3", "D4") == 4
      and 10 - _miss_b5("THEIA_E3", "D1") == 5
      and 10 - _miss_b5("THEIA_E3", "D3") == 5
      and 10 - _miss_b5("THEIA_E3", "D4") == 6,
      str((_miss_b5("THEIA_E3", "D1"), _miss_b5("THEIA_E3", "D3"), _miss_b5("THEIA_E3", "D4"))))

# R3: D1 at b=0, benign processes on the attack day
def fps(ds, attack):
    return [r["fp_day"] for r in subset(ROWS, ds, attack, 0, "D1")]
cad_fp = fps("CADETS_E3", "Nginx_Backdoor_06") + fps("CADETS_E3", "Nginx_Backdoor_12") + fps("CADETS_E3", "Nginx_Backdoor_13")
the_fp = fps("THEIA_E3", "Firefox_Backdoor_Drakon_In_Memory") + fps("THEIA_E3", "Browser_Extension_Drakon_Dropper")
check("R3", min(cad_fp) == 0 and max(cad_fp) == 3 and min(the_fp) == 0 and max(the_fp) == 6,
      f"cadets {cad_fp} theia {the_fp}")

# R1. Event counts are fixed by the streams. The rate is printed and not judged.
timing = json.loads((RES / "timing_single.json").read_text(encoding="utf-8"))
by = {r["dataset"]: r for r in timing}
check("R1", int(by["CADETS_E3"]["n_events"]) == 1987981 and int(by["THEIA_E3"]["n_events"]) == 5002043,
      str({k: v["n_events"] for k, v in by.items()}))
print(
    "measured {:.0f} / {:.0f} ev/s (paper: 38463 / 54971 on the original server)".format(
        float(by["CADETS_E3"]["events_per_s"]), float(by["THEIA_E3"]["events_per_s"])
    )
)

print()
if failures:
    print(f"{len(failures)} failed")
    sys.exit(1)
print("all checks passed")
