# paper_numbers.md — 最终提交版论文的全部数字（v2，R0b 回填）

用途：公开仓库 `Brsacher/ICASSP_early` 的"论文数字 → 代码"映射基准，也是 `scripts/verify_numbers.py` 的断言表。
基准文本：ICASSP 2027 提交版 *Early Birds Catch Worms* ，仓库内副本 `ecpg_reports/paper/FINAL_submitted.pdf`。
版本：v2，2026-10-14。R0（2026-10）给出初版映射，R0b 回填全部"待填"行并打出原始数据；本版合并两者。每行状态只用四个值：`已核实` / `口径不同` / `论文有误` / `撤回`。

统一背景（Table 1、Fig. 3、Q1–Q3 共用）：VELOX、epoch 11、协议 P1、告警后归零（`reset`）、选定档 CADETS `q99+type`、THEIA `q99+kind`。
主要产物：`artifacts_ext/fa/v9/<数据集>/seed{0-4}/eval/eval_reset_<cap>_<prior>.json`；`ecpg_reports/run_logs/fa/v9/{TABLE1_reset.md, per_cell_reset.csv, figA_reset_CADETS_E3.json, timing_single.json}`；`ecpg_reports/v9-6/DECOMP_v9_6.{md,json}`；`ecpg_reports/v9-11/{THEIA_diag.md, PERSIST_three_scorers.md}`。

---

## 0. 协议与设计常量

| 编号 | 论文位置 | 论文数字 | 源值 | 脚本 / 常量 | 状态 |
| --- | --- | --- | --- | --- | --- |
| C1 | §2 | t0 前 60 s 内且 t0 时仍 ≥ h 的告警计为 t0 | `PRE_T0_NS = 60e9` | `ecpg/fa9/config.py:19`；`alerts.py:first_tstar` | 已核实 |
| C2 | §2 | F：每测试日被 flag 且不属任何 P_i 的 process 数，先对测试日均值，再对 seed 取中位 | `mean_B` → `numpy.median` | `pipeline.py` 297–309；`table1.py` | 已核实 |
| C3 | §3 Baseline | δ_prog = max(75 分位, 均值)；程序名验证日事件 < 100 退回事件类型 | `N_MIN_KIND = 100` | `rent.py:57-82`；`config.py:17` | 已核实 |
| C4 | §3 Baseline | m(e) 从第 6 个同类型事件起 | `WARMUP = 5` | `rent.py:85-100`；`config.py:18` | 已核实 |
| C5 | §3 Increment | cap c = 验证日正超额 99 分位 | `q99` of `x > 0` | `rent.py:103-112` | 已核实 |
| C6 | §3 Update | fan-out 运行计数；routine = 1 + 当天此前同键 link 数；创建键 (父程序名, 子程序名)，交接键 (写者, 读者, 对象类型) | 同 | `rules.py:113-194` | 已核实 |
| C7 | §3 Calibration | h_k(b) 刚高于第 b+1 大的验证日每进程最大值 | `h = nextafter(xs[b], +inf)`，`xs` 降序 | `calibrate.py:26-34` `h_from_max` | 已核实 |
| C8 | §3 Calibration | 开关选择：D2、D3 在 b=2 的阈值在多数 seed 上与 D1 相差 ≤ 2 倍 | C1：CADETS 4/5，THEIA 5/5 | 两份 `selection.json` | 已核实 |
| C9 | §4 Rules | 预算网格 {0,1,2,5,10,20,50} | `BUDGETS = (0,1,2,5,10,20,50)` | `config.py:10` | 已核实 |
| C10 | §4 Detector | 五个 seed；N = 15 / 10；用最后一个 epoch | `num_epochs: 12`；落盘 epoch 0,1,3,5,7,9,11，11 为最后；`featurization.seed` = `training.seed` = 0–4；`encoder.used_methods: none`；lr CADETS 1e-4、THEIA 1e-3 | 十份 `run_config.yml`（`num_epochs` ≈ L701，`training.seed` ≈ L708，`featurization.seed` ≈ L250，`encoder` ≈ L694） | 已核实 |

---

## 1. 摘要与引言

| 编号 | 论文位置 | 论文数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- | --- |
| A1 | 摘要、贡献 (3)、Q1 | 14/15 对 9/15（b=5，CADETS） | both 8 + 仅 FA 6 = 14；both 8 + 仅 D1 1 = 9 | `decomp_v9_6.py` → `DECOMP_v9_6.json:4-8` | 已核实 |
| A2 | 摘要 | 漏检攻击上 FA 的均值进度 25% | 仅 FA 的 6 格 mean ρ = 0.2537202380952381 | `DECOMP_v9_6.json:108-111` | 已核实 |
| A3 | 摘要、贡献 (3)、Q1 | 27% 对 52% | 1 − 0.7279761904761907 = 0.2720；1 − 0.4828373015873016 = 0.5172 | `figA_reset_CADETS_E3.json` 键 `"5"` | 已核实 |
| A4 | 贡献 (3)、Q1 | D1@b=20 仍只检出 10 对 | both 9 + 仅 D1 1 | `DECOMP_v9_6.json:114-118` | 已核实 |

---

## 2. Fig. 1（CADETS，6 April，seed 1，D1@b=0）

| 编号 | 图中数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| F1-1 | t0 = 11:20，t1 = 12:09 | t0 = 1523028000000000000，t1 = 1523030940000000000（相差 2940 s） | `artifacts_ext/fa/v8/CADETS_E3/groundtruth.json`，`Nginx_Backdoor_06` | 已核实 |
| F1-2 | 21 个恶意事件，2 个恶意 process | \|P\| = 2，\|M\| = 21。导出用 **seed 1**（规则：seed 0 的 D1@b=0 未中，seed 1、3 同时有 D1@b=0 与 D3@b=2，取最小），v8.1 冻结档 `q99+type` | `ecpg/fa/exports/make_fig1_export.py:143-170`；`ecpg_reports/run_logs/2026-09-15_fig1_export.md:26`；`meta.json:196` | 已核实 |
| F1-3 | t* = t0 + 529 s，第 9 个恶意事件，ρ = 9/21 | v8 导出与 v9 reset + P1 的 seed 1 D1@b=0 相同：`n_seen=9`，`rho_e=0.42857142857142855`，`delay_t0=528.956163948` | `meta.json:56-60`；`artifacts_ext/fa/v9/CADETS_E3/seed1/eval/eval_reset_q99_type.json` | 已核实 |
| F1-4 | 边标签分组 | 21 行顺序：Rc,W,Rc,W；C,S,Rc,Rc,S；W,O；E；C,S,Rc；C,S；Rc,S,Rc,S | `artifacts_ext/exports/fig1_cadets_0406/m0_events.csv:2-22` | 已核实 |

README 里要写明：Fig. 1 取 seed 1；/tmp/vUgefal 的首次 write 在 t0 + 709.886 s，是第 10 个恶意事件，晚于图中 D1 的首告警（第 9 个，529 s）。

---

## 3. Table 1（b = 5）

每格为五个 seed 的中位数；ρ、d 只对检出 seed；k/5 = 检出 seed 数。源文件 `TABLE1_reset.md:7-42`。

| 编号 | 行 | D1 ρ (k/5) | D1 d | D3 ρ (k/5) | D3 d | Ours ρ (k/5) | Ours d | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | A1 = Nginx_06 | 0.24 (2/5) | 271 | 0.29 (5/5) | 174 | 0.29 (5/5) | 174 | 已核实 |
| T2 | A2 = Nginx_12 | 0.28 (4/5) | 254 | 0.10 (4/5) | 83 | 0.12 (5/5) | 83 | 已核实 |
| T3 | A3 = Nginx_13 ‡ | 0.06 (3/5) | 111 | 0.34 (3/5) | 251 | 0.20 (4/5) | 181 | 已核实 |
| T4 | A4 = THEIA Firefox | 0.31 (1/5) | 330 | 0.00 (1/5) | 32 | 0.16 (2/5) | 181 | 已核实 |
| T5 | A5 = THEIA Dropper ‡ | 0.01 (4/5) | 2 | 0.44 (4/5) | 619 | 0.22 (4/5) | 311 | 已核实 |

| 编号 | 行 | D1 | D3 | Ours | 源值 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| T6 | E CADETS（检出对数/15） | 0.48 (9) | 0.60 (12) | 0.73 (14) | 0.4828 / 0.5969 / 0.7280 | 已核实 |
| T7 | E THEIA（检出对数/10） | 0.42 (5) | 0.27 (5) | 0.43 (6) | 0.4246 / 0.2705 / 0.4252 | 已核实 |
| T8 | F CADETS | 5.0 | 12.0 | 12.0 | 5 / 12 / 12 | 已核实 |
| T9 | F THEIA | 10.7 | 16.3 | 20.0 | 10.6667 / 16.3333 / 20 | 已核实 |

---

## 4. Fig. 3（CADETS，21 个点，(F, E)）

脚本 `ecpg_reports/paper/make_fig3_v4.py`，输入 `figA_reset_CADETS_E3.json`。E = 15 对均值，F = 测试日均值再对 seed 中位。

| b | D1 (F, E) | D3 (F, E) | FirstAlarm (F, E) | 状态 |
| --- | --- | --- | --- | --- |
| 0 | 0.25, 0.3852 | 0.50, 0.0476 | 1.00, 0.4328 | 已核实 |
| 1 | 1.00, 0.4203 | 2.25, 0.1770 | 2.50, 0.4664 | 已核实 |
| 2 | 1.25, 0.4203 | 3.25, 0.1612 | 4.25, 0.4699 | 已核实 |
| 5 | 5.00, 0.4828 | 12.00, 0.5969 | 12.00, 0.7280 | 已核实 |
| 10 | 6.75, 0.5453 | 22.75, 0.6455 | 22.75, 0.7671 | 已核实 |
| 20 | 15.00, 0.5453 | 34.50, 0.6986 | 34.50, 0.8188 | 已核实 |
| 50 | 41.00, 0.6513 | 65.50, 0.8708 | 66.25, 0.9292 | 已核实 |

---

## 5. §4 Setup / Data / Detector / Rules

| 编号 | 论文位置 | 论文数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- | --- |
| D1 | Setup | Python 3.9、PyTorch 1.13.1、CUDA 11.7；i9-13900K、128 GB、两块 RTX 4090、Debian 13 | 容器 Python 3.9.25、torch 1.13.1+cu117；CPU/GPU/系统一致；`free -g` 读数 125 GiB（安装 128 GiB 的正常可用值，非勘误） | `ecpg_reports/environment/ENVIRONMENT.md:9-13,36,70-71` | 已核实 |
| D2 | Data | A1 (6 April; 2, 21) | P=2，M=21 | CADETS `groundtruth.json`；M 用 seed 0 `test_2018-04-06.npz` 按 `mi_indices` 数 | 已核实 |
| D3 | Data | A2 (12 April; 24, 96) | P=24，M=96 | 同上，`test_2018-04-12.npz` | 已核实 |
| D4 | Data | A3 (13 April; 14, 32) | P=14，M=32 | 同上，`test_2018-04-13.npz` | 已核实 |
| D5 | Data | A4 (10 April; 47, 173) | P=47，M=173 | THEIA `groundtruth.json`，`Firefox_Backdoor_Drakon_In_Memory` | 已核实 |
| D6 | Data | A5 (12 April; 49, 156) | P=49，M=156 | 同上，`Browser_Extension_Drakon_Dropper` | 已核实 |
| D7 | Data | spike-start 定义："the detector's own rule, on the seeds where it detects them, alerts within their first two malicious events" | D1@b=0：A3 的检出 seed 1、3 都在 `n_seen=2`；A5 的 seed 3、4 在 `n_seen=1`，但 **seed 0 在 `n_seen=148`**（ρ=0.9487，d=2224 s）。标签实际按检出 seed 的 n_seen 中位数定（A5 中位 1） | `THEIA_E3/seed{0,3,4}/eval/eval_reset_q99_kind.json`，`rows["0"]["D1"]` | 论文有误（E4） |
| D8 | Rules | b<5 时 FA 与 D1 的 E 差 ≤ 0.05 | 0.047619 / 0.046032 / 0.049603 | `figA_reset_CADETS_E3.json` | 已核实 |
| D9 | Rules | 表中省略 D2：b=5 CADETS 上 D2 与 D3 只差两对 | `n_changed=2` | `DECOMP_v9_6.json` 步 `D2→D3` | 已核实 |
| D10 | Rules | CADETS 只开 cap；THEIA 两开关全开 | `q99+type` / `q99+kind` | 两份 `selection.json` | 已核实 |

---

## 6. Q1

| 编号 | 论文数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| Q1-1 | E 0.48 → 0.73；进度 0.27 对 0.52 | 同 A3 | | 已核实 |
| Q1-2 | b=20 时 D1 的 F 15 对 FA 的 12，仍只 10 对 | 15.0 / 12.0；10 | `figA` JSON；`DECOMP` `FA@5_vs_D1@20` | 已核实 |
| Q1-3 | 相对默认阈值 D1：更早 4、相同 4、D1 无告警 6 | `FA@5_vs_D1@0`：4/4/0 + 仅 FA 6 | `DECOMP_v9_6.json` | 已核实（"6" 是仅 FA，不是更晚） |
| Q1-4 | 这 6 对：0.25，261 s | 0.2537 / 261.08 s | `DECOMP_v9_6.json:108-111` | 已核实 |
| Q1-5 | 两者都检出的 8 对：0.20 对 0.21 | FA 0.19475446428571427 / D1 0.21186755952380953（逐格见附录 B） | `DECOMP_v9_6.json:11-43` + 各 seed `rows["5"]` | 论文有误（E1） |
| Q1-6 | A2：FA "(ρ = 0.12, 83 s) on all five seeds" | 五 seed 都检出；`n_seen` = 12, 7, 12, 38, 7；`delay_t0` = 83.17, 82.88, 83.17, **984.15**, 82.88 s。中位 ρ 0.125、中位延迟 83.17 s 正确；seed 3 在第 38 事件、D1 通道 | `CADETS_E3/seed{0-4}/eval/eval_reset_q99_type.json`，`Nginx_Backdoor_12.rows["5"]["D4"]` | 口径不同（E5） |
| Q1-7 | A2：D1 第 27 事件（ρ = 0.28，254 s），4 seed | seed 0–3：`n_seen=27`，`rho_e=0.28125`，`delay_t0=254.106`；seed 4 未检出 | 同文件 `rows["5"]["D1"]` | 已核实 |
| Q1-8 | A1：FA 5/5，D1 2/5；中位第 6 事件（ρ = 0.29，174 s） | FA `n_seen` = 1, 6, 12, 9, 3（中位 6）；ρ 中位 0.285714；延迟 12.10, 173.60, 796.54, 528.96, 173.28 s（中位 173.60）。D1 只中 seed 1（n=9, 528.96 s）和 seed 3（n=1, 12.10 s） | `Nginx_Backdoor_06.rows["5"]` | 已核实 |
| Q1-9 | A1 首告警早于被释放可执行文件的写入 | /tmp/vUgefal 首次 WRITE 在 t0 + 709.886158284 s（第 10 个恶意事件）。中位告警 173.60 s 早于它；seed 2 的 796.54 s 晚于它（论文写的是中位，成立） | `m0_events.csv:11`；`meta.json:385` | 已核实 |
| Q1-10 | A3：4/5 对 3/5 | Table 1 行 T3 | `TABLE1_reset.md:19` | 已核实 |

---

## 7. Q2

| 编号 | 论文数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| Q2-1 | ladder 0.48 / 0.59 / 0.60 / 0.73 | 0.4828373 / 0.5874008 / 0.5969246 / 0.7279762 | `DECOMP_v9_6.json:608-629` | 已核实 |
| Q2-2 | D1→D2 "moves the A2 alert from the twenty-seventh malicious event to the tenth on four seeds" | D1 检出 seed 0/1/2/3，都在第 27 事件。D2 检出 seed 0/1/2/4，事件序号 **12、7、12、7**；seed 3 由检出变漏检。"第十"是中位 ρ 0.09896×96 ≈ 9.5 反推，数据里没有这一格 | `DECOMP_v9_6.json` 步 `D1→D2`；各 seed `rows["5"]["D2"]` | 论文有误（E6） |
| Q2-3 | D1→D2 "detects two more seeds of A1" | D1 中 seed 1、3；D2 中 seed 0、1、2、4。净增 2 = 新增 3（0,2,4）− 丢失 1（3） | 同一步 | 口径不同（E7） |
| Q2-4 | A3 上 D2 ρ = 0.34，D1 为 0.06 | 11/32 = 0.34375；2/32 = 0.0625 | `TABLE1_reset.md:19` | 已核实 |
| Q2-5 | D2→D3 只改 A1 两对：一对新检出，一对晚六个事件 | seed 2：ρ 0.2857 → 0.5714，`n_seen` 6 → 12；seed 3：未检出 → 0.5714，`n_seen` = 12 | `DECOMP_v9_6.json` 步 `D2→D3` | 已核实 |
| Q2-6 | 37 个首告警（b∈{2,5}）：20 来自 memory、34 含恶意事件、7 跨 process | 通道 D3=20、D1=17；34/37；7/37。**范围是 CADETS（25）+ THEIA（12）**，不只 CADETS | `DECOMP_v9_6.md:129-134`；JSON `C` 段 L912–925 | 已核实（E8 澄清） |
| Q2-7 | D3→FA 四个 cell；F 仍 12 | Nginx_06 s3 0.5714→0.4286；Nginx_12 s3 miss→0.3958；Nginx_13 s1 0.34375→0.0625；Nginx_13 s3 miss→0.0625；F 12.0→12.0 | `DECOMP_v9_6.json` 步 `D3→D4` | 已核实 |

---

## 8. Q3

| 编号 | 论文数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| Q3-1 | D1 b=0→50：F 0.25→41，E 0.39→0.65 | 0.25 / 41.0；0.3852 / 0.6513 | `figA` JSON | 已核实 |
| Q3-2 | FA 0.73 @ F 12（b=5）；D1 0.55 @ F 15（b=20） | 0.7280 / 12；0.5453 / 15 | 同上 | 已核实 |
| Q3-3 | b ≥ 10 时 FA 15/15 | b=10 `n_miss=0` | 同上 | 已核实 |
| Q3-4 | memory 通道测试日 12.0，D1 5.0 | Table 1 行 T8 | | 已核实 |
| Q3-5 | A2：memory 通道 83 s 告警；"fewer than 1% of the 83-s windows over the web server's earlier activity" | **攻击日 04-12、t0 前、nginx、D3@b=5、步长 10 s**：五 seed 的 83 s 窗命中率 8/2110、9/2110、19/2110、8/2110、9/2110，最大 0.0090 < 1%。（R0 曾把 04-06 seed 2 的 0.0606 误记为 A2 的值；A1 与 A2 两句同为攻击日口径，论文无误） | `decomp_v9_6.py:42,484-537`；`DECOMP_v9_6.json` `D.attack_days`；附录 A | 已核实（E2 撤回） |
| Q3-6 | A1：延迟 12–797 s；命中率 ≤ 16% | 五 seed 延迟 12.10 / 173.60 / 796.54 / 528.96 / 173.28 s；等长窗命中率最大 0.1592920（seed 2，36/226） | 同上 | 已核实 |
| Q3-7 | t0 前告警计入误报后 F 12.0 → 12.5 | F′ = 12.5000 | `DECOMP_v9_6.md:219-220` | 已核实 |
| Q3-8 | （未印）t0 前告警 1–9 次 | `n_pre` = 1,1,4,2,9,5,3,1,5,2 | 同 `D` | 已核实 |

---

## 9. Scope（§4 末段）

| 编号 | 论文数字 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| S1 | 两开关全开：0.73 → 0.59，F = 7.0 | 0.5869，7.0000 | `TABLE1_reset_q99_kind.md:27-28` | 已核实 |
| S2 | THEIA 0.43 对 0.42 | 0.4252 / 0.4246 | `TABLE1_reset.md:35-37` | 已核实 |
| S3 | THEIA 误报约两倍 | 20.0 / 10.6667 = 1.875 | `TABLE1_reset.md:36,38` | 已核实 |
| S4 | 4/5 seed 上 h3(5) ≤ 2c；测试日告警最多的程序验证日不出现 | h3/c = 2.000, 7.000, 2.000, 1.796, 2.000；firefox、fluxbox `in_val = 0` | `THEIA_diag.md:15-21`，B3/B4 | 已核实 |
| S5 | A4 多出的 seed：32 s 告警，早于任何恶意事件，证据链无恶意事件 | **seed 2**：`delay_t0=31.825`，`n_seen=0`，`chain_has_M=false`，`trig=nM`，通道 D3；链 `n_events=82`，`n_malicious=0` | `THEIA_E3/seed2/eval/eval_reset_q99_kind.json`；`DECOMP_v9_6.md:168` | 已核实 |

---

## 10. Discussion（§5；论文只写 "showed no gain"，数字只在仓库里）

| 编号 | 内容 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| X1 | ORTHRUS：D1@b=5 检出 5/15；FA E 0.08 对 D1 0.17 | 0.0820 / 0.1682 | `run_fa_v9_8.py` → `RESULTS_v9_8_orthrus.md:11-14` | 已核实 |
| X2 | KAIROS：D1@b=5 检出 2/15；FA 0/15 | both 0 + 仅 D1 2 | `run_fa_v9_5.py` → `RESULTS_v9_5_kairos.md:18` | 已核实 |
| X3 | 恶意事件中超过 baseline 的比例中位数：VELOX 43%、ORTHRUS 33%、KAIROS 25% | 0.4286 / 0.3333 / 0.2500（仅 M_i 子序列，n=155；附录 C） | `PERSIST_three_scorers.md:27-36` | 已核实 |
| X4 | ORTHRUS 判据预注册 | commit `2913926`，2026-09-20 05:02:38 EDT；seed 0 训练 05:09:57 启动 | `PROTOCOL_v9.md`；`orthrus_seeds/RUN_LOG.md` | 已核实 |
| X5 | 论文 "under a criterion fixed beforehand" 同时覆盖 KAIROS | `git log -S 'Kairos'` 与 `-S '0.1'` 在 PROTOCOL 只命中 `2913926`（05:02:38）；代码里的判据句最早 commit `54d3700`（03:50:37）；v9-5 重放 03:43:30–03:47:57。**开跑前没有任何书面 KAIROS 判据** | 第 3 节 | 论文有误（E3） |

---

## 11. 只进 README、不在论文里的数字

| 编号 | 内容 | 源值 | 脚本 / 输出 | 状态 |
| --- | --- | --- | --- | --- |
| R1 | 吞吐：CADETS 38k、THEIA 55k 事件/秒（单进程，七个预算） | 38463.2177；54971.1166 | `run_fa_v9_3 --phase timing` → `timing_single.json:11,23` | 已核实 |
| R2 | 保真度：b=0 时 D1 的 process 集合与 VELOX 原生告警，CADETS 每 seed 一致，THEIA 只差 CLONE 子进程（seed 3 七个，seed 4 一个） | `d1_vs_pth` ALL_PASS | `ecpg/fa/selfcheck.py:133-182`；`run_logs/fa/v8/RUN_LOG.md:7,37` | 已核实 |
| R3 | D1@b=0 攻击日良性误报：CADETS 0–3，THEIA 0–6 | CADETS 04-06: 0,2,0,0,0；04-12: 1,3,1,0,1；04-13: 0。THEIA 04-10: 0,0,1,0,0；04-12: 4,0,5,6,5 | `eval_reset_*.json` `rows["0"]["D1"]["fp_day"]` | 已核实 |

---

## 12. 勘误表（arXiv 版 / camera-ready 用）

| 编号 | 位置 | 论文写法 | 应为 / 处理 | 严重程度 | 状态 |
| --- | --- | --- | --- | --- | --- |
| E1 | Q1 | "(0.20 against 0.21)" | "(0.19 against 0.21)" | 次要 | 确认 |
| E2 | Q3 | placebo 两句口径不同 | **撤回**。A2 攻击日 83 s 窗最大 0.009 < 1%；A1 等长窗最大 0.159 ≤ 16%；两句同为攻击日 t0 前口径。R0 把 04-06 的 0.0606 误记为 A2 | — | 撤回 |
| E3 | §5 | "under a criterion fixed beforehand" 覆盖 ORTHRUS 与 KAIROS | 只对 ORTHRUS 成立。改为 "under a criterion fixed before the ORTHRUS run"，或分开写：ORTHRUS pre-registered；KAIROS 判据在重放之后写定。仓库 `PREREGISTRATION.md` 按事实写两个时间 | 重要 | 确认 |
| E4 | §4 Data | spike-start 定义 "the detector's own rule, on the seeds where it detects them, alerts within their first two malicious events" | A5 的 seed 0 在第 148 个事件。改为 "the median first alert of the detector's own rule, over the seeds where it detects them, falls within their first two malicious events"。‡ 标签不变 | 次要 | 新增 |
| E5 | Q1 | A2 "(ρ = 0.12, 83 s) on all five seeds" | 四个 seed 在 83 s（第 7–12 事件），seed 3 在 984 s（第 38 事件，detector 通道）；印出的是中位数。改为 "on all five seeds, at the median during the first burst of malicious events (ρ = 0.12, 83 s)" | 次要 | 新增 |
| E6 | Q2 | "moves the A2 alert from the twenty-seventh malicious event to the tenth on four seeds" | D2 检出 seed 0/1/2/4 的事件序号是 12、7、12、7；seed 3 由检出变漏检；"第十"在数据里不存在。改为 "moves the A2 alert from the twenty-seventh malicious event to the seventh or twelfth on three seeds, newly detects a fourth seed, and loses one" | 重要 | 新增 |
| E7 | Q2 | "detects two more seeds of A1" | 净增 2 = 新增 seed 0/2/4、丢失 seed 3。改为 "raises the A1 count from two seeds to four" | 次要 | 新增 |
| E8 | Q2 | "over the 37 first alerts of FirstAlarm at b ∈ {2, 5}"，置于 CADETS 段落 | 37 = CADETS 25 + THEIA 12。加 "on both hosts" | 次要（澄清） | 新增 |
| E9 | §1 P2 | "no PIDS evaluation reports how far an attack has progressed … under a false-positive budget" | 窄义成立。2026-10 文献核查建议收窄措辞，并点明三类相邻报告（processing latency、per-stage 检出、campaign recall / TTFD）。所引文献需自行核实后再用 | 重要（arXiv） | 新增 |
| E10 | §1 P3 | "the alert rules of recent learned detectors carry no evidence forward" | KAIROS 队列、NodLink、CAPTAIN 均跨时间或实体聚合。保留末句窄义陈述（"none accumulates the event-level scores of a learned detector toward a first alert"），首句软化为 "judge each score on its own at the event or node level"。NodLink / CAPTAIN 原文需自行核实 | 重要（arXiv） | 新增 |

---

## 附录 A. placebo 原始表（`decomp_v9_6.py:42,484-537`）

定义：CADETS、`q99+type`、`reset`、记忆通道 D3、b=5、滑动步长 10 s；进程为当天出现、程序名 nginx、且属于该日 P_i 的进程（10 格 `n_mal_proc` 均为 1）；命中率算 t0 之前。

| seed | 日 | L (s) | 攻击日 p(L) | 攻击日 p(83) |
| --- | --- | --- | --- | --- |
| 0 | 04-06 | 12.096 | 0.0 (0/304) | 0.0 (0/297) |
| 0 | 04-12 | 83.166 | 0.00379 (8/2110) | 0.00379 (8/2110) |
| 1 | 04-06 | 173.596 | 0.08333 (24/288) | 0.04714 (14/297) |
| 1 | 04-12 | 82.876 | 0.00427 (9/2110) | 0.00427 (9/2110) |
| 2 | 04-06 | 796.536 | **0.15929** (36/226) | 0.06061 (18/297) |
| 2 | 04-12 | 83.166 | **0.00900** (19/2110) | 0.00900 (19/2110) |
| 3 | 04-06 | 528.956 | 0.14229 (36/253) | 0.05724 (17/297) |
| 3 | 04-12 | 984.146 | 0.01931 (39/2020) | 0.00379 (8/2110) |
| 4 | 04-06 | 173.276 | 0.09375 (27/288) | 0.05724 (17/297) |
| 4 | 04-12 | 82.876 | 0.00427 (9/2110) | 0.00427 (9/2110) |

非攻击日 p(83)（全部 nginx 进程；04-10 验证日，04-11、04-13 测试日）：seed 0–4 在 04-10 为 无告警 / 0.00504 / 0.00840 / 0.00471 / 0.00471；04-11 仅 seed 0 有 0.00450；04-13 无起点。论文未用这组数。

## 附录 B. 八个共检出 cell（`DECOMP_v9_6.json:11-43`）

| 攻击 | seed | FA ρ | D1 ρ |
| --- | --- | --- | --- |
| Nginx_06 | 1 | 0.2857142857 | 0.4285714286 |
| Nginx_06 | 3 | 0.4285714286 | 0.0476190476 |
| Nginx_12 | 0 | 0.125 | 0.28125 |
| Nginx_12 | 1 | 0.0729166667 | 0.28125 |
| Nginx_12 | 2 | 0.125 | 0.28125 |
| Nginx_12 | 3 | 0.3958333333 | 0.28125 |
| Nginx_13 | 1 | 0.0625 | 0.0625 |
| Nginx_13 | 3 | 0.0625 | 0.03125 |

均值 0.19475446 / 0.21186756。

## 附录 C. 三 scorer 恶意子序列（`PERSIST_three_scorers.md:27-36`，n=155）

| 量 | VELOX 中位 / 均值 | KAIROS 中位 / 均值 | ORTHRUS 中位 / 均值 |
| --- | --- | --- | --- |
| frac_pos | 0.4286 / 0.4003 | 0.2500 / 0.2434 | 0.3333 / 0.2559 |
| max_W_over_h3 | 0.2845 / 0.3508 | 0.0007 / 0.0209 | 0.0929 / 0.1320 |

## 附录 D. 冻结输入的生成代码（R1 必须保留的 `ecpg/fa` 模块）

| 模块 | 输入 | 输出 |
| --- | --- | --- |
| `stream.py` | PIDSMaker `edge_losses/{split}/model_epoch_11/*.csv`（`loss,srcnode,dstnode,time,edge_type`）；`indexid2msg.pkl` | `artifacts_ext/fa/v8/<数据集>/seed*/stream/<split>_<day>.npz` + `.meta.json` |
| `paths.py` | `run_logs/velox_seeds/SUMMARY_data.json` | CSV/pkl 路径 |
| `etypes.py` | `pidsmaker.utils.dataset_utils.rel2id_darpa_tc` | 边类型编号 |
| `names.py`、`timeutil.py`、`config.py` | 无外部文件 | 程序名、纳秒/日期、`EPOCH=11` |
| `db.py` | Postgres `cadets_e3` / `theia_e3`，只读 | 无 |
| `lineage.py` | `SELECT … FROM event_table WHERE operation='EVENT_FORK'` | `lineage.json`（THEIA 为空，创建边来自分流 CLONE） |
| `groundtruth.py` | `Ground_Truth/orthrus/*.csv`；三张节点表；`pidsmaker.config` 攻击窗 | `groundtruth.json` |
| `selfcheck.py` | 冻结分流 + VELOX `.pth` | R2 的保真度检查 |

数据包体量：VELOX 分流 CADETS 715,097,130 + THEIA 1,498,969,410 字节；KAIROS edge_losses 691,817,077；ORTHRUS edge_losses 667,783,518；`fa/v9_kairos` 690,749,362；`fa/v9_orthrus` 690,750,924；GT、lineage、selection 合计约 11 MB。
