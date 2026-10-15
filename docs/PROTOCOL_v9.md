# PROTOCOL_v9（评估协议 P1 + 三种再报变体）

日期：2026-09-18。阶段 v9-3 更新表口径与标签（第 2、6 条）；规则与 P1 的 t* / ρ / FP 定义仍为 v9-2。实现目录 `ecpg/fa9/`。`ecpg/fa` 与 `artifacts_ext/fa/v8` 只读。

## 2 规则

与 v8.2 一致的部分原样复制，不得改动：基线 δ、n_kind≥100 的先验回退、第 6 条起的实例中位数（进程×etype 的 running median，与表上对 seed 的聚合中位无关，后者见第 6 条）、cap=q99、Δ 的截断、W 更新、创建/交接候选公式、运行累计的 fan-out 与 routine、候选取 max、证据指针。

唯一的两处修改：

a. 创建快照：创建候选用父进程在创建事件之前的 W（不含创建事件自身的 Δ），CADETS 的 fork 与 THEIA 的 CLONE 统一。

b. 再报变体 `--rearm` ∈ {below, reset, fir}，只作用于 D2/D3（D1 不变，每条 s≥h 都报）：

- below = v8.2 现状：W 自下方穿过 h 报警，回落到 h 以下后才能再报；
- reset = 报警时 W←0（Page 1954），证据链从下一事件重新起根；
- fir = 报警时 W←h/2（Lucas & Crosier 1982 的 fast initial response），证据链同样重新起根。

三个变体里 m(e)、计数、快照逻辑都不动；孩子继承的是父进程当时的 W（reset 后就是 0 或 h/2）。

D4 = D1@h1(0) ∪ D3@h3(b)，t* 取两通道较早者，记录胜出通道。

## 3 校准

不变。h(b) 仍用验证日无阈值轨迹的每进程最大值排序取 m_{b+1} 之上一点；b=0 的 D1 阈值算法不变；四档 (cap × prior) 全部校准，选定档判据 C1 不变；另外把「两开关全开」档（q99+kind）作为固定的第二档一并跑测试日。测试日回放对 reset/fir 必须按每个 b 单独回放（W 轨迹依赖 h），below 可复用无阈值轨迹。

## 4 评估 P1

a. t* = 攻击窗内 P_i 进程上最早的报警，t ≥ t0；宽限：[t0−60 s, t0) 内的报警且该进程统计量在 t0 时仍 ≥ h，记为 t0。删除 already 逻辑，不得以任何形式把 t0 之前的报警记为检出。

b. t0 之前 P_i 进程上的报警：不算检出，不算误报。

c. ρ = |{e∈M_i: t(e)≤t*}|/|M_i|；d = t*−t0 秒；miss 则 ρ 记 1 进 earliness、表中写 miss。

d. 攻击日 FP = 当日被标记的非 P_i 进程数；F = 各测试日均值（04-11 只剔除首次报警落在旧窗 [15:07,15:16] 内的进程），再对 seed 取中位（numpy.median，偶数个取中间两值均值；见第 6 条）。

e. earliness = 全部攻击×seed 单元 (1−ρ) 的均值。

f. quiet/spike 标签用 D1@h1(0)，规则见第 6 条。标签与论文分组（6 Apr、12 Apr、THEIA 10 Apr 为 quiet；13 Apr、THEIA 12 Apr 为 spike）不一致时在回报里单列，不得手工改。

g. †：D2/D3 的命中，从报警事件沿指针回溯到根，链中无 M_i 事件；D1 的命中，触发事件 ∉ M_i；D4 按胜出通道。同时按 (规则, b) 统计 k/n = 链含 M_i 的命中数 / 命中数。

## 5 输出

根目录 `artifacts_ext/fa/v9/`，报告目录 `ecpg_reports/run_logs/fa/v9/`。

a. 每个变体一张 Table 1：`TABLE1_<variant>.md` 与 `.tex`（tabular 行）。行 = 攻击 × b∈{2,5}，按 quiet/spike 分块；列 = D1/D2/D3/FirstAlarm 各三项：ρ (k/5)（ρ 为检出 seed 的中位）、d（中位）、FP（攻击日中位）；中位口径见第 6 条；ρ 上加 † 标；每行在「检出 seed 最多」的规则里把最小 ρ 与最小 d 加粗；底栏每个数据集的 earliness (miss 数) 在 b=2、5，以及 F 在 b=2/5。变体 = below（选定档）、reset（选定档）、fir（选定档）、reset（两开关全开档）。四张表的 D1 列必须逐格相同。

b. 图 A 数据：每个变体每个数据集 `figA_<variant>_<DS>.json`，键 (b, rule) → {earliness, n_miss, n, F_median}，b 全网格 {0,1,2,5,10,20,50}。

c. 逐格 CSV `per_cell_<variant>.csv`：数据集、攻击、seed、b、规则、hit、tstar、flag(window/pre60)、rho、delay、fp_day、channel、trig(M/nM)、chain_has_M。

d. 诊断 `DIAG_standing_<variant>.md`：对每个数据集、seed、攻击日、b∈{2,5}、每个 P_i 进程：当天首次 W≥h3(b) 的时刻、t0 时 W/h、t0 前的报警次数、窗内首次报警时刻；reset/fir 变体另给窗内 W 轨迹的极值。验证日和非攻击日上同程序名（nginx、firefox）是否被标记也各给一行。

e. 吞吐：每个数据集每个 seed 每个变体的测试日回放墙钟与 events/s，写 `timing.json`。该 events/s 是单个 `test_seed` 进程的 n_events/wall，不是 8 workers 分摊。

## 6 表口径与标签（v9-3）

中位数口径：所有对检出 seed 取中位的量（ρ、d）以及攻击日 FP、F 对 seed 的中位，一律用 `numpy.median`（偶数个取中间两值均值）。ρ 表内写两位小数，d 四舍五入为整数秒。

标签规则（D1@h1(0)）：

- spike-start = 至少一个 seed 检出，且检出 seed 上「t* 时已见恶意事件数」的中位数 ≤ 2；
- quiet-start = 无 seed 检出，或检出 seed 上 ρ 的中位数 ≥ 0.25；
- 两条同时成立或两条都不成立 → mid。

v9-3 另写 `EVIDENCE_<variant>.md`、DIAG 告警量附录、图 A PDF/CSV、投稿格式 `TABLE1_{reset,below,fir}.tex`。不改第 2 条的 W / 再报 / 快照，不改第 4 条 a–c、e、g 的 P1 定义。

## ORTHRUS（第三 scorer）

范围：CADETS E3；seed 0–4；PIDSMaker 自带 ORTHRUS tuned 配置，不改超参；取最后一个 epoch 的逐边 loss；重放用 fa9（reset、P1）不改；THEIA 不跑。
标定：基线 δ、cap c、各阈值用 ORTHRUS 的验证日（2018-04-10）分数按原方法重算；四个 (cap, prior) 组合按 C1 选；C1 无组合达到 4/5 时取中位 fold 最小者（calibrate.py 既有行为）；q99+type 同时报告；选择过程不读测试期结果。
主判据（与 Kairos 相同）：以 C1 选中组合为准，gain ⇔ E_FA(b=5) − E_D1(b=5) ≥ 0.1 且 F_FA(b=5) ≤ F_D1(b=20)。
信号判据：signal ⇔ PIDSMaker 自身在最后一个 epoch 的节点级 evaluation 至少在 3/5 个 seed 上标记到 ≥1 个 GT 节点。
四种结局与固定措辞（数字按结果填，句式不改）：
(1) gain：With ORTHRUS's per-event scores the gain holds: at $b=5$ FirstAlarm reaches an earliness score of [X] against [Y] for the event-level rule, at $F=$[..] against [..] at $b=20$.
(2) 无 gain 且有 signal：With ORTHRUS's per-event scores, which separate the attacks (the event-level rule detects [k] of the 15 pairs at $b=5$), FirstAlarm adds no gain ([X] against [Y]), so the gain is shown only with VELOX's scores.
(3) 无 gain 且无 signal：With ORTHRUS's per-event scores the event-level rule detects [k] of the 15 pairs at $b=5$ and FirstAlarm [k'], as with Kairos's.
(4) pipeline failure（前置检查不过、训练或重放出错、或截止时间前没有任何重放结果）：论文不提 ORTHRUS。
报告义务：只要重放产生了结果，无论哪种结局都写进论文；Kairos 的结果照常报告。
截止：训练核对 北京时间 2026-09-21 23:59（服务器 EDT 09-21 11:59）；重放核实 北京时间 2026-09-22 18:00（EDT 09-22 06:00）。到训练截止时已核对通过的 seed 不少于 3 个，则只用这些 seed 并在文中写明 seed 数。
不做：改分数变换、改规则、改预算网格、换 epoch、换超参。
