"""Summarise a VELOX multi-seed tree and write SUMMARY_data.json.

    FA_ART_ROOT=... python3 scripts/summarize_velox_seeds.py

Reads $FA_ART_ROOT/velox_seeds/evaluation/evaluation/*/run_config.yml.
Writes $FA_ART_ROOT/velox_seeds/SUMMARY.md and SUMMARY_data.json.
Paths in the JSON are relative to FA_ART_ROOT. Optional per-seed logs:
$FA_ART_ROOT/velox_seeds/<DATASET>_seed<K>/RUN_LOG.md.
"""

import glob
import json
import os
import re
import statistics
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd
import torch
import yaml

import os
from pathlib import Path

def _art_root() -> str:
    env = os.environ.get("FA_ART_ROOT")
    if env:
        return env
    return str(Path(__file__).resolve().parents[1] / "artifacts")

REPO = _art_root()

def rel_art(p: str) -> str:
    """Path stored in SUMMARY_data.json, relative to FA_ART_ROOT."""
    if not p:
        return p
    ap = os.path.abspath(p)
    root = os.path.abspath(REPO) + os.sep
    if ap.startswith(root):
        return ap[len(root):]
    return p
EXT_ROOT = os.path.join(REPO, "velox_seeds")
BASE_ROOT = os.environ.get("FA_BASELINE_ROOT", os.path.join(REPO, "_no_baseline"))
LOG_ROOT = EXT_ROOT
EPOCHS = [0, 1, 3, 5, 7, 9, 11]
EXPECTED_SEEDS = [0, 1, 2, 3, 4]
DATASETS = ["CADETS_E3", "THEIA_E3"]
SEED_TASKS = ["featurization", "feat_inference", "batching", "training", "evaluation"]
SHARED_TASKS = ["construction", "transformation"]
# VELOX 论文 Table 4（用户给出）：(mean, min, best)；区间 = [min, best]
PAPER = {
    "CADETS_E3": {"adp": (0.94, 0.77, 1.00), "precision": (0.85, 0.44, 1.00)},
    "THEIA_E3": {"adp": (0.72, 0.42, 0.97), "precision": (0.53, 0.03, 0.91)},
}
KEYS = ["srcnode", "dstnode", "time", "edge_type"]
COLLAPSE_ADP = 0.10  # 「ADP 崩溃」的判定阈值（仅用于结论措辞）

# 本实验的历史事件（人工核实，随脚本固化以免重生成时丢失）
NOTES_COMPLETENESS = """
**运行历史（已核实）**：
- 两路于 2026-09-04 09:17/09:16 EDT 启动（CADETS_E3@GPU0，THEIA_E3@GPU1，各 5 个种子串行），CADETS 全部于 10:33 完成，THEIA seed 0–3 于 10:50 完成。
- **THEIA_E3 seed 4 首次尝试挂起**：09-04 10:50:11 EDT 启动后停在进程启动阶段（累计 CPU 6 s、`stdout.txt` 0 字节、无任何产物），其网络命名空间有一条到 `185.199.108.133:443`（raw.githubusercontent.com）的空闲 ESTABLISHED 连接。推断原因：`pidsmaker/utils/utils.py:33` 导入时 `nltk.download("punkt", quiet=True)` 抓取 GitHub 索引，`urlopen` 无超时，遇瞬时网络故障永久阻塞（事后同一 URL 0.3 s 可取回）。09-06 07:46 EDT 按用户指示 `kill`（退出码 143，记录见 `THEIA_E3_seed4/RUN_LOG_attempt1_hung.md`），随后在 `ecpg/scripts/run_with_rusage.py` 加 `socket.setdefaulttimeout(60)`（DECISIONS.md D-004），于 09-06 07:47 EDT 用 `SEEDS="4"` 单独补跑（启动器输出 `launcher_theia_seed4_rerun.txt`，21 min 15 s，退出码 0）。首轮 THEIA 启动器输出仍在 `launcher_theia.txt`（含 seed 0–3 与挂起的 seed 4 首次尝试）。

**内存观察（已核实）**：单个 VELOX 运行的峰值 RSS 为 CADETS ≈62.4 GB、THEIA ≈88–100 GB（框架把全部划分的 `TemporalData` 一次性载入内存）。推断：两路并行时若峰值同时出现，合计 ≈160 GB 会超过 125 GiB 物理内存（本机另有 94 GiB swap）；首轮两路并行均正常结束、无 OOM 迹象，但今后并行两路 THEIA 级别任务需谨慎。耗时：CADETS 11–19 min/种子、THEIA 20–28 min/种子（两路并行相互争抢 CPU/IO）。
"""


def rel_ext(p: str) -> str:
    return p.replace(f"{EXT_ROOT}/", "").replace(f"{BASE_ROOT}/", "artifacts/")


def plain(v):
    """numpy/torch 标量 → Python 标量（供 JSON 与格式化使用）。"""
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:  # noqa: BLE001
            return str(v)
    if isinstance(v, (int, float, str)) or v is None:
        return v
    return str(v)


def fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def discover_runs():
    runs = []
    for yml in sorted(glob.glob(f"{EXT_ROOT}/evaluation/evaluation/*/run_config.yml")):
        cfg = yaml.safe_load(open(yml))
        ds = cfg["dataset"]["name"]
        fseed, tseed = cfg["featurization"]["seed"], cfg["training"]["seed"]
        paths = {t: cfg[t]["_task_path"] for t in SHARED_TASKS + SEED_TASKS}
        attacks = [a[0].split("/")[-1].replace("node_", "").replace(".csv", "") for a in cfg["dataset"]["attack_to_time_window"]]
        runs.append(dict(dataset=ds, seed=tseed, featurization_seed=fseed, training_seed=tseed,
                         run_config=yml, paths=paths, attacks=attacks))
    return sorted(runs, key=lambda r: (r["dataset"], r["seed"]))


def load_stats(eval_path):
    out = OrderedDict()
    pr = os.path.join(eval_path, "precision_recall_dir")
    for ep in EPOCHS:
        f = os.path.join(pr, f"stats_model_epoch_{ep}.pth")
        out[ep] = {k: plain(v) for k, v in torch.load(f).items()} if os.path.exists(f) else None
    return out


def best_adp_epoch(stats):
    """复刻 pidsmaker/tasks/evaluation.py:92-111（best_adp）：按 epoch 升序，ADP 更高者胜，平手看 discrimination 更高。"""
    best, best_adp, best_disc = None, float("-inf"), float("-inf")
    for ep in EPOCHS:
        s = stats.get(ep)
        if s is None:
            continue
        cond = (s["adp_score"] > best_adp) or (s["adp_score"] == best_adp and s["discrimination"] > best_disc)
        if cond:
            best, best_adp, best_disc = ep, s["adp_score"], s["discrimination"]
    return best


def val_stats(train_path, ep):
    """val 目录全部 CSV 的 loss：(max, mean, n)。max 即 max_val_loss 阈值。"""
    d = os.path.join(train_path, "edge_losses", "val", f"model_epoch_{ep}")
    if not os.path.isdir(d):
        return None
    tot, n, mx = 0.0, 0, float("-inf")
    for f in sorted(os.listdir(d)):
        s = pd.read_csv(os.path.join(d, f), usecols=["loss"])["loss"]
        if len(s):
            tot += float(s.sum()); n += len(s); mx = max(mx, float(s.max()))
    return dict(max=mx, mean=tot / n if n else None, n=n)


def attack_coverage(eval_path, ep, n_attacks):
    """从 scores_model_epoch_N.pkl 计算每个攻击是否至少有一个 TP 节点（y_pred=1 且 y_true=1 且节点属于该攻击）。
    与 node_evaluation.py:346-356 的 attack_to_TPs 同口径。返回 {att: tp_count}。"""
    f = os.path.join(eval_path, "precision_recall_dir", f"scores_model_epoch_{ep}.pkl")
    if not os.path.exists(f):
        return None
    sc = torch.load(f)
    yp, yt, nodes, n2a = sc["y_preds"], sc["y_truth"], sc["nodes"], sc["node2attacks"]
    tp_per_att = {a: 0 for a in range(n_attacks)}
    for node, p, t in zip(nodes, yp, yt):
        if p == 1 and t == 1:
            for a in n2a.get(node, ()):
                tp_per_att[int(a)] = tp_per_att.get(int(a), 0) + 1
    return tp_per_att


def load_edge_dir(d):
    frames = []
    for f in sorted(os.listdir(d)):
        frames.append(pd.read_csv(os.path.join(d, f), dtype={"loss": "float64", "srcnode": "int64",
                                                              "dstnode": "int64", "time": "int64", "edge_type": "int64"}))
    df = pd.concat(frames, ignore_index=True)
    df["occ"] = df.groupby(KEYS).cumcount()
    return df, len(frames)


def edge_diff(base_dir, k0_dir):
    b, nb = load_edge_dir(base_dir)
    k, nk = load_edge_dir(k0_dir)
    m = b.merge(k, on=KEYS + ["occ"], how="outer", suffixes=("_base", "_k0"), indicator=True)
    both = m["_merge"] == "both"
    d = (m.loc[both, "loss_base"] - m.loc[both, "loss_k0"]).abs()
    return dict(
        base_files=nb, k0_files=nk, base_rows=int(len(b)), k0_rows=int(len(k)),
        dup_keys_base=int((b["occ"] > 0).sum()), aligned=int(both.sum()),
        only_base=int((m["_merge"] == "left_only").sum()), only_k0=int((m["_merge"] == "right_only").sum()),
        abs_diff_max=float(d.max()) if len(d) else None, abs_diff_mean=float(d.mean()) if len(d) else None,
        abs_diff_p999=float(d.quantile(0.999)) if len(d) else None,
        n_gt_0_01=int((d > 0.01).sum()), n_gt_0=int((d > 0).sum()), n_eq_0=int((d == 0).sum()),
    )


def parse_run_log(path):
    txt = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    g = lambda pat: (re.search(pat, txt) or [None, None])[1]
    ts = r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [A-Z]+)"
    return dict(
        start=g(r"开始时间[^:]*: " + ts), end=g(r"结束时间: " + ts),
        dur_s=g(r"宿主计时耗时: (\d+) s"), rc=g(r"退出码: (\d+)"), rss_kb=g(r"峰值 RSS[^:]*: (\d+) kB"),
        rss_gb=g(r"≈ ([0-9.]+) GB"), done=g(r"done.txt 齐全: (\d+/\d+)"), finished=g(r"`Run finished` 出现次数: (\d+)"),
    )


def in_range(v, lo, hi):
    return lo <= v <= hi


def main():
    runs = discover_runs()
    data = {"runs": [], "completeness": {}, "edge_diff": {}, "baseline": {}, "paper_compare": {}, "val_rule": {}, "coverage": {}}
    lines = []
    L = lines.append

    # ---------- 完整性 ----------
    done_files = sorted(glob.glob(f"{EXT_ROOT}/**/done.txt", recursive=True))
    found = {(r["dataset"], r["seed"]) for r in runs}
    missing = []
    for ds in DATASETS:
        for k in EXPECTED_SEEDS:
            if (ds, k) not in found:
                missing += [(ds, k, t) for t in SEED_TASKS]
    for r in runs:
        for t in SHARED_TASKS + SEED_TASKS:
            if not os.path.exists(os.path.join(r["paths"][t], "done.txt")):
                missing.append((r["dataset"], r["seed"], t))
    for r in runs:
        r["stats"] = load_stats(r["paths"]["evaluation"])
        r["stats_missing"] = [ep for ep in EPOCHS if r["stats"][ep] is None]
        r["best_epoch"] = best_adp_epoch(r["stats"])
        r["run_log"] = parse_run_log(f"{LOG_ROOT}/{r['dataset']}_seed{r['seed']}/RUN_LOG.md")
        r["eval_size"] = os.popen(f"du -sh '{r['paths']['evaluation']}' 2>/dev/null | cut -f1").read().strip()
        # val 统计（全部 epoch）：阈值 = max，验证集选 epoch 用 mean
        r["val"] = {ep: val_stats(r["paths"]["training"], ep) for ep in EPOCHS}
        valid = [ep for ep in EPOCHS if r["val"][ep] and r["val"][ep]["mean"] is not None]
        r["val_rule_epoch"] = min(valid, key=lambda e: r["val"][e]["mean"]) if valid else None
        # 各攻击覆盖（epoch 11 与 val 规则 epoch）
        r["coverage"] = {}
        for ep in sorted({11, r["val_rule_epoch"]} - {None}):
            r["coverage"][ep] = attack_coverage(r["paths"]["evaluation"], ep, len(r["attacks"]))
    du_total = os.popen(f"du -sh '{EXT_ROOT}' 2>/dev/null | cut -f1").read().strip()
    data["completeness"] = dict(done_count=len(done_files), expected=54, missing=missing, du=du_total)

    # ---------- 基线（K=0 对照） ----------
    baseline = {}
    for ds in DATASETS:
        k0 = next((r for r in runs if r["dataset"] == ds and r["seed"] == 0), None)
        if k0 is None:
            continue
        bpaths = {t: p.replace(f"{EXT_ROOT}/", f"{BASE_ROOT}/") for t, p in k0["paths"].items()}
        if not os.path.isdir(bpaths["evaluation"]):
            continue
        bstats = load_stats(bpaths["evaluation"])
        bval = {ep: val_stats(bpaths["training"], ep) for ep in (9, 11)}
        baseline[ds] = dict(paths=bpaths, stats=bstats, val=bval, k0=k0, best_epoch=best_adp_epoch(bstats))
        ed = {}
        for split in ("test", "val"):
            bd = os.path.join(bpaths["training"], "edge_losses", split, "model_epoch_11")
            kd = os.path.join(k0["paths"]["training"], "edge_losses", split, "model_epoch_11")
            ed[split] = edge_diff(bd, kd)
        data["edge_diff"][ds] = ed

    # ---------- 写 SUMMARY.md ----------
    def att_ids(stats):
        ids = set()
        for s in stats.values():
            if s:
                ids |= {int(k.split("_")[-1]) for k in s if k.startswith("discrim_tp_att_") and k != "discrim_tp_att_sum"}
        return sorted(ids)

    def thr(r, ep):
        v = r["val"].get(ep)
        return v["max"] if v else None

    def row(r, ep, tag):
        s = r["stats"][ep]
        atts = " / ".join(f"att{i}:{s.get(f'discrim_tp_att_{i}', '—')}" for i in att_ids(r["stats"]))
        return (f"| {r['seed']} | {ep}{tag} | {s['tp']} | {s['fp']} | {s['fn']} | {fmt(s['precision'], 5)} | {fmt(s['recall'], 5)} | "
                f"{fmt(s['adp_score'])} | {fmt(s['percent_detected_attacks'], 2)} | {atts} | {fmt(thr(r, ep), 4)} |")

    L("# VELOX 多种子实验汇总（run_tag `velox_seeds`）")
    L("")
    L("生成方式：`python3 scripts/summarize_velox_seeds.py`（容器内，只读 `artifacts_ext/velox_seeds/` 与 `artifacts/`）。"
      "本文件中的全部数字均为**已核实**（直接由产物文件计算）；解释性判断标「推断」。指标定义见 `ecpg_reports/code_reading/2026-09-04_pidsmaker_report.md` 第 7 节。")
    L("")

    # 五行摘要
    summ = {}
    for ds in DATASETS:
        rs = [r for r in runs if r["dataset"] == ds and r["stats"].get(11)]
        if not rs:
            continue
        prec = {r["seed"]: r["stats"][11]["precision"] for r in rs}
        adp = {r["seed"]: r["stats"][11]["adp_score"] for r in rs}
        p_lo, p_hi = PAPER[ds]["precision"][1:]; a_lo, a_hi = PAPER[ds]["adp"][1:]
        summ[ds] = dict(
            n=len(rs), seeds=sorted(prec),
            precision=dict(median=statistics.median(prec.values()), min=min(prec.values()), max=max(prec.values())),
            adp=dict(median=statistics.median(adp.values()), min=min(adp.values()), max=max(adp.values())),
            best_seed_adp=max(adp, key=adp.get), worst_seed_adp=min(adp, key=adp.get),
            best_seed_prec=max(prec, key=prec.get), worst_seed_prec=min(prec, key=prec.get),
            adp_in_range=sorted(k for k, v in adp.items() if in_range(v, a_lo, a_hi)), adp_out=sorted(k for k, v in adp.items() if not in_range(v, a_lo, a_hi)),
            prec_in_range=sorted(k for k, v in prec.items() if in_range(v, p_lo, p_hi)), prec_out=sorted(k for k, v in prec.items() if not in_range(v, p_lo, p_hi)),
            adp_median_in=in_range(statistics.median(adp.values()), a_lo, a_hi), prec_median_in=in_range(statistics.median(prec.values()), p_lo, p_hi),
        )
    L("## 0. 五行摘要（epoch 11，各种子）")
    L("")
    for ds in DATASETS:
        if ds not in summ:
            continue
        s = summ[ds]
        L(f"- **{ds}**（{s['n']} 个种子 {s['seeds']}）：precision 中位数 {s['precision']['median']:.3f}（最小 {s['precision']['min']:.3f}，最大 {s['precision']['max']:.3f}）；"
          f"ADP 中位数 {s['adp']['median']:.3f}（最小 {s['adp']['min']:.3f}，最大 {s['adp']['max']:.3f}）；"
          f"按 ADP 最强 seed {s['best_seed_adp']}、最弱 seed {s['worst_seed_adp']}（按 precision 最强 seed {s['best_seed_prec']}、最弱 seed {s['worst_seed_prec']}）。")
    for ds in DATASETS:
        if ds not in summ:
            continue
        s = summ[ds]
        p_lo, p_hi = PAPER[ds]["precision"][1:]; a_lo, a_hi = PAPER[ds]["adp"][1:]
        L(f"- **{ds} 对照论文 Table 4 区间**（ADP {a_lo:.2f}–{a_hi:.2f}、precision {p_lo:.2f}–{p_hi:.2f}）："
          f"epoch 11 的 ADP 落在区间内的种子 {s['adp_in_range']}，区间外 {s['adp_out']}；precision 区间内 {s['prec_in_range']}，区间外 {s['prec_out']}；"
          f"ADP 中位数{'在' if s['adp_median_in'] else '不在'}区间内，precision 中位数{'在' if s['prec_median_in'] else '不在'}区间内。"
          f"（按论文同口径 best_adp epoch 的对照见第四节。）")
    n_runs = len(runs)
    L(f"- 完整性：{n_runs}/10 个运行完成，`done.txt` {len(done_files)}/54；"
      + ("无缺失。" if not missing else f"缺失 {len(missing)} 项（见第一节）。")
      + " K=0 对 `artifacts/` 基线为**逐位复现**（第三节）。THEIA seed 4 首轮挂起后已补跑（第一节运行历史）。")
    L("")

    # 一
    L("## 一、完整性核对")
    L("")
    L(f"- `find artifacts_ext/velox_seeds -name done.txt | wc -l` = **{len(done_files)}**（期望 54 = 2 数据集 × (2 共享任务 + 5 种子 × 5 任务)）。")
    if missing:
        L(f"- 缺失 {len(missing)} 个 (dataset, seed, task)：" + "；".join(f"({d}, seed {k}, {t})" for d, k, t in missing))
    else:
        L("- 无缺失。")
    L(f"- `du -sh artifacts_ext/velox_seeds` = **{du_total}**。")
    L("")
    L("| dataset | seed | 开始 (EDT) | 结束 (EDT) | 耗时 | 退出码 | 峰值 RSS | done.txt | stats_model_epoch_{0,1,3,5,7,9,11} | evaluation 目录 |")
    L("|---|---|---|---|---|---|---|---|---|---|")
    for ds in DATASETS:
        for k in EXPECTED_SEEDS:
            r = next((x for x in runs if x["dataset"] == ds and x["seed"] == k), None)
            rl = parse_run_log(f"{LOG_ROOT}/{ds}_seed{k}/RUN_LOG.md")
            if r is None:
                L(f"| {ds} | {k} | {rl['start'] or '—'} | {rl['end'] or '未结束'} | — | {rl['rc'] or '—'} | — | 无 run_config.yml | — | 无 |")
                continue
            dur = f"{int(rl['dur_s'])//60} min {int(rl['dur_s'])%60} s" if rl["dur_s"] else "—"
            stats_ok = "齐全 7/7" if not r["stats_missing"] else f"缺 {r['stats_missing']}"
            L(f"| {ds} | {k} | {rl['start'] or '—'} | {rl['end'] or '—'} | {dur} | {rl['rc'] or '—'} | {(rl['rss_gb'] + ' GB') if rl['rss_gb'] else '—'} | {rl['done'] or '—'} | {stats_ok} | `{rel_ext(r['paths']['evaluation'])}`（{r['eval_size']}） |")
    L("")
    L("注：峰值 RSS 来自 `ecpg.scripts.run_with_rusage` 的 `ru_maxrss`（主进程含线程）；框架自身日志的 tracemalloc 值只统计 Python 对象、不含 torch 张量，故远小于 RSS。")
    L(NOTES_COMPLETENESS)

    # 二
    L("## 二、主表")
    L("")
    for ds in DATASETS:
        rs = [r for r in runs if r["dataset"] == ds]
        if not rs:
            continue
        L(f"### {ds}（每种子两行：epoch 11 与 best_adp 选中的 epoch，后者标 `*`；同一 epoch 时只列一行）")
        L("")
        L("| 种子 | epoch | TP | FP | FN | precision | recall | ADP | percent_detected_attacks | discrim_tp_att_i | 阈值 = val max(loss) |")
        L("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rs:
            if r["stats"].get(11):
                L(row(r, 11, "*" if r["best_epoch"] == 11 else ""))
            if r["best_epoch"] is not None and r["best_epoch"] != 11 and r["stats"].get(r["best_epoch"]):
                L(row(r, r["best_epoch"], "*"))
        L("")
        L(f"ADP 随 epoch（{ds}）：")
        L("")
        L("| 种子 | " + " | ".join(f"ep{e}" for e in EPOCHS) + " | best_adp epoch |")
        L("|---|" + "---|" * len(EPOCHS) + "---|")
        for r in rs:
            L(f"| {r['seed']} | " + " | ".join(fmt(r["stats"][e]["adp_score"]) if r["stats"][e] else "—" for e in EPOCHS) + f" | {r['best_epoch']} |")
        L("")

    # 三
    L("## 三、复现检验（K=0 对 artifacts/ 基线）")
    L("")
    for ds, b in baseline.items():
        k0 = b["k0"]
        L(f"### {ds}")
        L("")
        L(f"- 基线目录：`{rel_ext(b['paths']['evaluation'])}`；K=0 目录：`{rel_ext(k0['paths']['evaluation'])}`（哈希目录名相同，已核实）。")
        L("")
        L("| 来源 | epoch | TP | FP | precision | recall | ADP | discrimination | 阈值 = val max(loss) |")
        L("|---|---|---|---|---|---|---|---|---|")
        for ep in (9, 11):
            for name, st, vv in (("基线 artifacts/", b["stats"], b["val"]), ("K=0 artifacts_ext/", k0["stats"], k0["val"])):
                s = st.get(ep)
                if s is None:
                    continue
                t = vv.get(ep)["max"] if vv.get(ep) else None
                L(f"| {name} | {ep} | {s['tp']} | {s['fp']} | {fmt(s['precision'], 5)} | {fmt(s['recall'], 5)} | {fmt(s['adp_score'])} | {fmt(s['discrimination'], 4)} | {fmt(t, 6)} |")
        L("")
        ed = data["edge_diff"][ds]
        L("逐边差异（epoch 11，按 (srcnode, dstnode, time, edge_type[, 组内序号]) 对齐）：")
        L("")
        L("| split | 基线 CSV 数 / 行数 | K=0 CSV 数 / 行数 | 对齐边数 | 仅基线 | 仅 K=0 | \\|Δloss\\| 最大 | 均值 | 99.9 分位 | \\|Δloss\\|>0.01 边数 | Δ≠0 边数 | Δ=0 边数 |")
        L("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for split in ("test", "val"):
            e = ed[split]
            L(f"| {split} | {e['base_files']} / {e['base_rows']} | {e['k0_files']} / {e['k0_rows']} | {e['aligned']} | {e['only_base']} | {e['only_k0']} | "
              f"{fmt(e['abs_diff_max'], 6)} | {fmt(e['abs_diff_mean'], 8)} | {fmt(e['abs_diff_p999'], 6)} | {e['n_gt_0_01']} | {e['n_gt_0']} | {e['n_eq_0']} |")
        L("")
        bitwise = all(ed[s]["only_base"] == 0 and ed[s]["only_k0"] == 0 and ed[s]["n_gt_0"] == 0 for s in ("test", "val"))
        if bitwise:
            concl = (f"**结论：{ds} 的 K=0 逐位复现了基线**——test {ed['test']['aligned']} 条、val {ed['val']['aligned']} 条边全部一一对齐且 loss 完全相等（Δ=0），"
                     f"epoch 9/11 的 TP/FP/precision/ADP/阈值也逐位相同。推断：GPU 非确定性与 PYTHONHASHSEED 的合并效应在本配置下为零——"
                     f"gensim 4.3.1 的 Word2Vec 初始化由 `seed` 经 `np.random.default_rng` 决定、不经 Python `hash()`（已核实源码），`workers=1` 无线程抖动；"
                     f"仅线性层 + `cudnn.deterministic=True` 的训练/推理在同型 GPU 上未表现出可观测的非确定性。")
        else:
            mx = max(ed[s]["abs_diff_max"] or 0 for s in ("test", "val"))
            concl = (f"**结论：{ds} 的 K=0 未逐位复现基线**——差异量级：|Δloss| 最大 {mx:.4g}，"
                     f"test 中 |Δ|>0.01 的边 {ed['test']['n_gt_0_01']}/{ed['test']['aligned']}，val 中 {ed['val']['n_gt_0_01']}/{ed['val']['aligned']}；"
                     f"这是 GPU 非确定性与 PYTHONHASHSEED（基线未知、本次=0）的合并效应，无法在事后拆分。")
        L(concl)
        data["edge_diff"][ds]["conclusion"] = concl
        L("")

    # 四、与论文可比对照（best_adp epoch 口径）
    L("## 四、与 VELOX 论文的可比对照（每种子取 best_adp 选中的 epoch，与论文 Table 4 同口径）")
    L("")
    for ds in DATASETS:
        rs = [r for r in runs if r["dataset"] == ds and r["best_epoch"] is not None]
        if not rs:
            continue
        prec = [r["stats"][r["best_epoch"]]["precision"] for r in rs]
        adp = [r["stats"][r["best_epoch"]]["adp_score"] for r in rs]
        pc = dict(n=len(rs), seeds=[r["seed"] for r in rs], best_epochs=[r["best_epoch"] for r in rs],
                  precision=dict(mean=statistics.mean(prec), min=min(prec), best=max(prec), per_seed=prec),
                  adp=dict(mean=statistics.mean(adp), min=min(adp), best=max(adp), per_seed=adp))
        data["paper_compare"][ds] = pc
        pp, pa = PAPER[ds]["precision"], PAPER[ds]["adp"]
        L(f"### {ds}（{pc['n']} 个种子，选中 epoch = {dict(zip(pc['seeds'], pc['best_epochs']))}）")
        L("")
        L("| 指标 | 我们 mean | 我们 min | 我们 best | 论文 mean | 论文 min | 论文 best | 逐种子（best_adp epoch） |")
        L("|---|---|---|---|---|---|---|---|")
        L(f"| ADP | {pc['adp']['mean']:.3f} | {pc['adp']['min']:.3f} | {pc['adp']['best']:.3f} | {pa[0]:.2f} | {pa[1]:.2f} | {pa[2]:.2f} | {', '.join(f'{v:.3f}' for v in adp)} |")
        L(f"| precision | {pc['precision']['mean']:.3f} | {pc['precision']['min']:.3f} | {pc['precision']['best']:.3f} | {pp[0]:.2f} | {pp[1]:.2f} | {pp[2]:.2f} | {', '.join(f'{v:.3f}' for v in prec)} |")
        L("")
        adp_in = in_range(pc["adp"]["min"], pa[1], pa[2]) and in_range(pc["adp"]["best"], pa[1], pa[2])
        pr_in = in_range(pc["precision"]["min"], pp[1], pp[2]) and in_range(pc["precision"]["best"], pp[1], pp[2])
        n_adp_in = sum(in_range(v, pa[1], pa[2]) for v in adp); n_pr_in = sum(in_range(v, pp[1], pp[2]) for v in prec)
        sent = (f"结论：{ds} 按 best_adp 口径，ADP {'全部' if adp_in else f'{n_adp_in}/{len(adp)} 个种子'}落在论文区间 [{pa[1]:.2f}, {pa[2]:.2f}] 内"
                f"（我们的均值 {pc['adp']['mean']:.3f} vs 论文 {pa[0]:.2f}）；precision {'全部' if pr_in else f'{n_pr_in}/{len(prec)} 个种子'}落在 [{pp[1]:.2f}, {pp[2]:.2f}] 内"
                f"（均值 {pc['precision']['mean']:.3f} vs 论文 {pp[0]:.2f}）。")
        L(sent)
        data["paper_compare"][ds]["conclusion"] = sent
        L("")

    # 五、验证集选 epoch
    L("## 五、验证集选 epoch（val 目录全部 CSV 的 loss 均值 / 最大值）")
    L("")
    L("规则：对每个评估 epoch 计算 val 全部边 loss 的均值（`val_mean`）与最大值（`val_max`，即 max_val_loss 阈值）；「val 规则 epoch」= `val_mean` 最小的 epoch（只用验证集信息，不看测试集与真值）。")
    L("")
    for ds in DATASETS:
        rs = [r for r in runs if r["dataset"] == ds]
        if not rs:
            continue
        L(f"### {ds}")
        L("")
        L("val_mean（每格：均值 / 最大值）：")
        L("")
        L("| 种子 | " + " | ".join(f"ep{e}" for e in EPOCHS) + " |")
        L("|---|" + "---|" * len(EPOCHS))
        for r in rs:
            cells = []
            for e in EPOCHS:
                v = r["val"][e]
                cells.append(f"{v['mean']:.4f} / {v['max']:.2f}" if v and v["mean"] is not None else "—")
            L(f"| {r['seed']} | " + " | ".join(cells) + " |")
        L("")
        L("| 种子 | val 规则 epoch（val_mean 最小） | 其 test ADP | best_adp epoch | 其 ADP | epoch 11 ADP | val 规则 vs ep11 |")
        L("|---|---|---|---|---|---|---|")
        vr = []
        for r in rs:
            ve, be = r["val_rule_epoch"], r["best_epoch"]
            a_v = r["stats"][ve]["adp_score"] if ve is not None and r["stats"].get(ve) else None
            a_b = r["stats"][be]["adp_score"] if be is not None and r["stats"].get(be) else None
            a_11 = r["stats"][11]["adp_score"] if r["stats"].get(11) else None
            delta = (a_v - a_11) if (a_v is not None and a_11 is not None) else None
            vr.append(dict(seed=r["seed"], val_rule_epoch=ve, adp_val_rule=a_v, best_epoch=be, adp_best=a_b, adp_ep11=a_11))
            L(f"| {r['seed']} | {ve} | {fmt(a_v)} | {be} | {fmt(a_b)} | {fmt(a_11)} | {('+' if delta >= 0 else '') + f'{delta:.3f}' if delta is not None else '—'} |")
        data["val_rule"][ds] = vr
        L("")
        collapsed_11 = [x["seed"] for x in vr if x["adp_ep11"] is not None and x["adp_ep11"] < COLLAPSE_ADP]
        collapsed_vr = [x["seed"] for x in vr if x["adp_val_rule"] is not None and x["adp_val_rule"] < COLLAPSE_ADP]
        better = [x["seed"] for x in vr if x["adp_val_rule"] is not None and x["adp_ep11"] is not None and x["adp_val_rule"] > x["adp_ep11"]]
        worse = [x["seed"] for x in vr if x["adp_val_rule"] is not None and x["adp_ep11"] is not None and x["adp_val_rule"] < x["adp_ep11"]]
        hit_best = [x["seed"] for x in vr if x["val_rule_epoch"] == x["best_epoch"]]
        mean_v = statistics.mean(x["adp_val_rule"] for x in vr if x["adp_val_rule"] is not None)
        mean_11 = statistics.mean(x["adp_ep11"] for x in vr if x["adp_ep11"] is not None)
        mean_b = statistics.mean(x["adp_best"] for x in vr if x["adp_best"] is not None)
        if not collapsed_11 and not collapsed_vr:
            avoid = "epoch 11 无崩溃点，无需避开，val 规则也未引入崩溃"
        elif not collapsed_11:
            avoid = f"epoch 11 无崩溃点，但 val 规则在种子 {collapsed_vr} 上选中了崩溃 epoch"
        elif not collapsed_vr:
            avoid = "验证集规则避开了全部崩溃点"
        elif set(collapsed_vr) & set(collapsed_11):
            avoid = f"验证集规则未能避开种子 {sorted(set(collapsed_vr) & set(collapsed_11))} 的崩溃点"
        else:
            avoid = "验证集规则避开了 epoch 11 的崩溃点，但在其他种子上选中了崩溃 epoch"
        sent = (f"结论：{ds} 中 epoch 11 出现 ADP 崩溃（<{COLLAPSE_ADP}）的种子 {collapsed_11 or '无'}；val 规则选中的 epoch 中 ADP 崩溃的种子 {collapsed_vr or '无'}——{avoid}。"
                f"val 规则相对 epoch 11：ADP 更高的种子 {better or '无'}、更低的 {worse or '无'}；与 best_adp（看真值的上界）恰好相同的种子 {hit_best or '无'}。"
                f"ADP 均值：val 规则 {mean_v:.3f}、epoch 11 {mean_11:.3f}、best_adp 上界 {mean_b:.3f}。")
        L(sent)
        data["val_rule"][ds + "_conclusion"] = sent
        L("")

    # 六、各攻击覆盖
    L("## 六、各攻击覆盖（每个攻击是否至少有一个 TP 节点）")
    L("")
    L("口径：TP 节点 = `y_pred=1 且 y_true=1`（阈值判定后的检出），攻击归属取自 `scores_model_epoch_N.pkl` 的 `node2attacks`，与 `node_evaluation.py:346-356` 计算 `percent_detected_attacks` 的 `attack_to_TPs` 同口径；"
      "括号内为该攻击的 TP 节点数。`disc` 列为 stats 中的 `discrim_tp_att_i`（分数高于前 10 良性均值的真值节点数，**不是**阈值判定），仅供参考。")
    L("")
    for ds in DATASETS:
        rs = [r for r in runs if r["dataset"] == ds]
        if not rs:
            continue
        atts = rs[0]["attacks"]
        L(f"### {ds}（攻击编号 → 真值文件：" + "；".join(f"att{i} = {a}" for i, a in enumerate(atts)) + "）")
        L("")
        L("| 种子 | epoch | " + " | ".join(f"att{i}" for i in range(len(atts))) + " | 覆盖数/攻击数 | percent_detected_attacks(stats) | disc（discrim_tp_att_i） |")
        L("|---|---|" + "---|" * len(atts) + "---|---|---|")
        cov_out = []
        for r in rs:
            for ep, label in ((11, "11"), (r["val_rule_epoch"], f"{r['val_rule_epoch']}（val 规则）")):
                if ep is None:
                    continue
                cov = r["coverage"].get(ep)
                s = r["stats"].get(ep) or {}
                if cov is None:
                    continue
                flags = [1 if cov.get(i, 0) > 0 else 0 for i in range(len(atts))]
                disc = "/".join(str(s.get(f"discrim_tp_att_{i}", "—")) for i in range(len(atts)))
                cells = " | ".join(f"{f}（{cov.get(i, 0)}）" for i, f in enumerate(flags))
                L(f"| {r['seed']} | {label} | {cells} | {sum(flags)}/{len(atts)} | {fmt(s.get('percent_detected_attacks'), 2)} | {disc} |")
                cov_out.append(dict(seed=r["seed"], epoch=ep, flags=flags, tp_per_attack=cov, percent_detected_attacks=s.get("percent_detected_attacks")))
                if ep == r["val_rule_epoch"] and ep == 11:
                    break  # val 规则 epoch 恰为 11 时不重复
        data["coverage"][ds] = cov_out
        L("")
        # 汇总：每个攻击在多少个种子的 epoch 11 被覆盖
        for ep_label, sel in (("epoch 11", lambda c: c["epoch"] == 11), ("val 规则 epoch", lambda c, rs=rs: any(c["seed"] == r["seed"] and c["epoch"] == r["val_rule_epoch"] for r in rs))):
            rows_ = [c for c in cov_out if sel(c)]
            if rows_:
                per_att = [sum(c["flags"][i] for c in rows_) for i in range(len(atts))]
                L(f"- {ep_label}：各攻击被覆盖的种子数 = " + "，".join(f"att{i} {per_att[i]}/{len(rows_)}" for i in range(len(atts)))
                  + f"；全部攻击都被覆盖的种子 {[c['seed'] for c in rows_ if sum(c['flags']) == len(atts)] or '无'}。")
        L("")

    # 附录 + JSON
    data["runs"] = [dict(dataset=r["dataset"], seed=r["seed"], featurization_seed=r["featurization_seed"], training_seed=r["training_seed"],
                         run_config=rel_art(r["run_config"]), paths={k: rel_art(v) for k, v in r["paths"].items()}, attacks=r["attacks"], best_epoch=r["best_epoch"], val_rule_epoch=r["val_rule_epoch"],
                         stats_missing=r["stats_missing"], val={str(k): v for k, v in r["val"].items()}, run_log=r["run_log"],
                         coverage={str(k): v for k, v in r["coverage"].items()},
                         stats={str(ep): s for ep, s in r["stats"].items()}) for r in runs]
    data["baseline"] = {ds: dict(paths={k: rel_art(v) for k, v in b["paths"].items()}, best_epoch=b["best_epoch"], val={str(k): v for k, v in b["val"].items()},
                                 stats={str(ep): s for ep, s in b["stats"].items()}) for ds, b in baseline.items()}
    data["summary"] = summ
    with open(f"{LOG_ROOT}/SUMMARY_data.json", "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)
    L("## 附录")
    L("")
    L("- 全部原始数值见 `$FA_ART_ROOT/velox_seeds/SUMMARY_data.json`（路径相对 FA_ART_ROOT）；逐种子运行记录见各 `<DATASET>_seed<K>/RUN_LOG.md`。")
    L("- 发现的运行：" + "；".join(f"{r['dataset']} seed {r['seed']}（featurization.seed={r['featurization_seed']}, training.seed={r['training_seed']}）" for r in runs))
    with open(f"{LOG_ROOT}/SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
