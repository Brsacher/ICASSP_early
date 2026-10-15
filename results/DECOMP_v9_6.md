# DECOMP_v9_6

只读 v9-3 reset / P1。不改规则、不改 Table 1。

- 自检 A/B：ok=True flags=[]
- 自检 C：ok=True flags=[]
- CADETS b=5 E 原文：D1=0.482837 D2=0.587401 D3=0.596925 FA=0.727976
- 四舍五入：0.48 → 0.59 → 0.60 → 0.73。已核实。

## A cell 分解

### CADETS_E3

| 比较 | both | 仅FA | 仅D1 | 都未检出 | FA检出mean/med ρ | D1检出mean/med ρ | both FA/D1 meanρ | FA更早/同/更晚 | 仅FA meanρ/d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FA@5_vs_D1@5 | 8 | 6 | 1 | 0 | 0.22002551020408162/0.13392857142857142 | 0.19527116402116404/0.28125 | 0.19475446428571427/0.21186755952380953 | 4/1/3 | 0.2537202380952381/261.075665415 |
| FA@5_vs_D1@20 | 9 | 5 | 1 | 0 | 0.22002551020408162/0.13392857142857142 | 0.18199404761904764/0.171875 | 0.2113095238095238/0.19527116402116404 | 4/1/4 | 0.23571428571428568/263.1238678222 |
| FA@5_vs_D1@0 | 8 | 6 | 0 | 1 | 0.22002551020408162/0.13392857142857142 | 0.27771577380952384/0.28125 | 0.19475446428571427/0.27771577380952384 | 4/4/0 | 0.2537202380952381/261.075665415 |

#### FA@5_vs_D1@5 清单

- both (8): Nginx_Backdoor_06/s1, Nginx_Backdoor_06/s3, Nginx_Backdoor_12/s0, Nginx_Backdoor_12/s1, Nginx_Backdoor_12/s2, Nginx_Backdoor_12/s3, Nginx_Backdoor_13/s1, Nginx_Backdoor_13/s3
- fa_only (6): Nginx_Backdoor_06/s0, Nginx_Backdoor_06/s2, Nginx_Backdoor_06/s4, Nginx_Backdoor_12/s4, Nginx_Backdoor_13/s0, Nginx_Backdoor_13/s4
- d1_only (1): Nginx_Backdoor_13/s2
- none (0): —

#### FA@5_vs_D1@20 清单

- both (9): Nginx_Backdoor_06/s1, Nginx_Backdoor_06/s3, Nginx_Backdoor_12/s0, Nginx_Backdoor_12/s1, Nginx_Backdoor_12/s2, Nginx_Backdoor_12/s3, Nginx_Backdoor_13/s1, Nginx_Backdoor_13/s3, Nginx_Backdoor_13/s4
- fa_only (5): Nginx_Backdoor_06/s0, Nginx_Backdoor_06/s2, Nginx_Backdoor_06/s4, Nginx_Backdoor_12/s4, Nginx_Backdoor_13/s0
- d1_only (1): Nginx_Backdoor_13/s2
- none (0): —

#### FA@5_vs_D1@0 清单

- both (8): Nginx_Backdoor_06/s1, Nginx_Backdoor_06/s3, Nginx_Backdoor_12/s0, Nginx_Backdoor_12/s1, Nginx_Backdoor_12/s2, Nginx_Backdoor_12/s3, Nginx_Backdoor_13/s1, Nginx_Backdoor_13/s3
- fa_only (6): Nginx_Backdoor_06/s0, Nginx_Backdoor_06/s2, Nginx_Backdoor_06/s4, Nginx_Backdoor_12/s4, Nginx_Backdoor_13/s0, Nginx_Backdoor_13/s4
- d1_only (0): —
- none (1): Nginx_Backdoor_13/s2

### THEIA_E3

| 比较 | both | 仅FA | 仅D1 | 都未检出 | FA检出mean/med ρ | D1检出mean/med ρ | both FA/D1 meanρ | FA更早/同/更晚 | 仅FA meanρ/d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FA@5_vs_D1@5 | 5 | 1 | 0 | 4 | 0.29133936070352257/0.1592744923669779 | 0.15088928412627833/0.00641025641025641 | 0.34960723284422707/0.15088928412627833 | 0/3/2 | 0.0/31.824950275 |
| FA@5_vs_D1@20 | 5 | 1 | 0 | 4 | 0.29133936070352257/0.1592744923669779 | 0.15088928412627833/0.00641025641025641 | 0.34960723284422707/0.15088928412627833 | 0/3/2 | 0.0/31.824950275 |
| FA@5_vs_D1@0 | 4 | 2 | 0 | 4 | 0.29133936070352257/0.1592744923669779 | 0.3184192974655402/0.1592744923669779 | 0.190214169260412/0.3184192974655402 | 1/3/0 | 0.4935897435897436/1177.8894728055 |

#### FA@5_vs_D1@5 清单

- both (5): Browser_Extension_Drakon_Dropper/s0, Browser_Extension_Drakon_Dropper/s2, Browser_Extension_Drakon_Dropper/s3, Browser_Extension_Drakon_Dropper/s4, Firefox_Backdoor_Drakon_In_Memory/s0
- fa_only (1): Firefox_Backdoor_Drakon_In_Memory/s2
- d1_only (0): —
- none (4): Browser_Extension_Drakon_Dropper/s1, Firefox_Backdoor_Drakon_In_Memory/s1, Firefox_Backdoor_Drakon_In_Memory/s3, Firefox_Backdoor_Drakon_In_Memory/s4

#### FA@5_vs_D1@20 清单

- both (5): Browser_Extension_Drakon_Dropper/s0, Browser_Extension_Drakon_Dropper/s2, Browser_Extension_Drakon_Dropper/s3, Browser_Extension_Drakon_Dropper/s4, Firefox_Backdoor_Drakon_In_Memory/s0
- fa_only (1): Firefox_Backdoor_Drakon_In_Memory/s2
- d1_only (0): —
- none (4): Browser_Extension_Drakon_Dropper/s1, Firefox_Backdoor_Drakon_In_Memory/s1, Firefox_Backdoor_Drakon_In_Memory/s3, Firefox_Backdoor_Drakon_In_Memory/s4

#### FA@5_vs_D1@0 清单

- both (4): Browser_Extension_Drakon_Dropper/s0, Browser_Extension_Drakon_Dropper/s3, Browser_Extension_Drakon_Dropper/s4, Firefox_Backdoor_Drakon_In_Memory/s0
- fa_only (2): Browser_Extension_Drakon_Dropper/s2, Firefox_Backdoor_Drakon_In_Memory/s2
- d1_only (0): —
- none (4): Browser_Extension_Drakon_Dropper/s1, Firefox_Backdoor_Drakon_In_Memory/s1, Firefox_Backdoor_Drakon_In_Memory/s3, Firefox_Backdoor_Drakon_In_Memory/s4

## B ladder CADETS b=5

| 步 | ΔE | E after | n_changed |
| --- | --- | --- | --- |
| ∅→D1 | 0.482837 | 0.482837 | 9 |
| D1→D2 | 0.104563 | 0.587401 | 15 |
| D2→D3 | 0.009524 | 0.596925 | 2 |
| D3→D4 | 0.131052 | 0.727976 | 4 |

### ∅→D1

| attack | seed | ρ before | ρ after | hit before | hit after |
| --- | --- | --- | --- | --- | --- |
| Nginx_Backdoor_06 | 1 | None | 0.42857142857142855 | False | True |
| Nginx_Backdoor_06 | 3 | None | 0.047619047619047616 | False | True |
| Nginx_Backdoor_12 | 0 | None | 0.28125 | False | True |
| Nginx_Backdoor_12 | 1 | None | 0.28125 | False | True |
| Nginx_Backdoor_12 | 2 | None | 0.28125 | False | True |
| Nginx_Backdoor_12 | 3 | None | 0.28125 | False | True |
| Nginx_Backdoor_13 | 1 | None | 0.0625 | False | True |
| Nginx_Backdoor_13 | 2 | None | 0.0625 | False | True |
| Nginx_Backdoor_13 | 3 | None | 0.03125 | False | True |

### D1→D2

| attack | seed | ρ before | ρ after | hit before | hit after |
| --- | --- | --- | --- | --- | --- |
| Nginx_Backdoor_06 | 0 | None | 0.047619047619047616 | False | True |
| Nginx_Backdoor_06 | 1 | 0.42857142857142855 | 0.2857142857142857 | True | True |
| Nginx_Backdoor_06 | 2 | None | 0.2857142857142857 | False | True |
| Nginx_Backdoor_06 | 3 | 0.047619047619047616 | None | True | False |
| Nginx_Backdoor_06 | 4 | None | 0.14285714285714285 | False | True |
| Nginx_Backdoor_12 | 0 | 0.28125 | 0.125 | True | True |
| Nginx_Backdoor_12 | 1 | 0.28125 | 0.07291666666666667 | True | True |
| Nginx_Backdoor_12 | 2 | 0.28125 | 0.125 | True | True |
| Nginx_Backdoor_12 | 3 | 0.28125 | None | True | False |
| Nginx_Backdoor_12 | 4 | None | 0.07291666666666667 | False | True |
| Nginx_Backdoor_13 | 0 | None | 0.34375 | False | True |
| Nginx_Backdoor_13 | 1 | 0.0625 | 0.34375 | True | True |
| Nginx_Backdoor_13 | 2 | 0.0625 | None | True | False |
| Nginx_Backdoor_13 | 3 | 0.03125 | None | True | False |
| Nginx_Backdoor_13 | 4 | None | 0.34375 | False | True |

### D2→D3

| attack | seed | ρ before | ρ after | hit before | hit after |
| --- | --- | --- | --- | --- | --- |
| Nginx_Backdoor_06 | 2 | 0.2857142857142857 | 0.5714285714285714 | True | True |
| Nginx_Backdoor_06 | 3 | None | 0.5714285714285714 | False | True |

### D3→D4

| attack | seed | ρ before | ρ after | hit before | hit after |
| --- | --- | --- | --- | --- | --- |
| Nginx_Backdoor_06 | 3 | 0.5714285714285714 | 0.42857142857142855 | True | True |
| Nginx_Backdoor_12 | 3 | None | 0.3958333333333333 | False | True |
| Nginx_Backdoor_13 | 1 | 0.34375 | 0.0625 | True | True |
| Nginx_Backdoor_13 | 3 | None | 0.0625 | False | True |

## C evidence chain（37 个 FA 首告警）

- 链含 M_i：34/37；CADETS b=5：14/14
- 告警 process = 入口 process：17/37
- 跨 process：7/37
- 通道：{'D1': 17, 'D3': 20, 'D1+D3': 0}

| ds | attack | seed | b | ch | entry? | cross | n_ev | n_mal | malΔ/W |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CADETS_E3 | Nginx_Backdoor_06 | 0 | 2 | D3 | True | False | 188 | 0 | 0.0000 |
| CADETS_E3 | Nginx_Backdoor_06 | 0 | 5 | D3 | True | False | 33 | 1 | 0.2506 |
| CADETS_E3 | Nginx_Backdoor_12 | 0 | 2 | D3 | False | False | 78 | 1 | 0.1787 |
| CADETS_E3 | Nginx_Backdoor_12 | 0 | 5 | D3 | False | False | 50 | 6 | 0.6256 |
| CADETS_E3 | Nginx_Backdoor_13 | 0 | 2 | D3 | False | True | 23 | 15 | 1.1056 |
| CADETS_E3 | Nginx_Backdoor_13 | 0 | 5 | D3 | False | False | 7 | 7 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_06 | 1 | 2 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_06 | 1 | 5 | D3 | True | False | 105 | 5 | 0.5631 |
| CADETS_E3 | Nginx_Backdoor_12 | 1 | 2 | D1 | False | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_12 | 1 | 5 | D3 | False | False | 43 | 3 | 0.4694 |
| CADETS_E3 | Nginx_Backdoor_13 | 1 | 2 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_13 | 1 | 5 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_06 | 2 | 2 | D3 | False | True | 130 | 20 | 1.4652 |
| CADETS_E3 | Nginx_Backdoor_06 | 2 | 5 | D3 | False | True | 108 | 11 | 1.1247 |
| CADETS_E3 | Nginx_Backdoor_12 | 2 | 2 | D1 | False | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_12 | 2 | 5 | D3 | False | False | 14 | 7 | 0.6608 |
| CADETS_E3 | Nginx_Backdoor_06 | 3 | 2 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_06 | 3 | 5 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_12 | 3 | 2 | D1 | False | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_12 | 3 | 5 | D1 | False | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_13 | 3 | 2 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_13 | 3 | 5 | D1 | True | False | 1 | 1 | 1.0000 |
| CADETS_E3 | Nginx_Backdoor_06 | 4 | 5 | D3 | True | False | 93 | 3 | 0.4125 |
| CADETS_E3 | Nginx_Backdoor_12 | 4 | 5 | D3 | False | False | 36 | 1 | 0.2436 |
| CADETS_E3 | Nginx_Backdoor_13 | 4 | 5 | D3 | False | False | 8 | 7 | 0.9957 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 0 | 2 | D1 | False | False | 1 | 1 | 1.0000 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 0 | 5 | D1 | False | False | 1 | 1 | 1.0000 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 0 | 2 | D3 | False | True | 255 | 20 | 1.0026 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 0 | 5 | D3 | False | True | 255 | 20 | 1.0026 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 2 | 2 | D3 | True | True | 81 | 0 | 0.0000 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 2 | 5 | D3 | True | True | 82 | 0 | 0.0000 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 2 | 2 | D3 | False | False | 11 | 6 | 0.6878 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 2 | 5 | D3 | False | False | 11 | 6 | 0.6878 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 3 | 2 | D1 | True | False | 1 | 1 | 1.0000 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 3 | 5 | D1 | True | False | 1 | 1 | 1.0000 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 4 | 2 | D1 | True | False | 1 | 1 | 1.0000 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 4 | 5 | D1 | True | False | 1 | 1 | 1.0000 |

## D placebo CADETS b=5

| seed | day | d_cell | n_pre | first | mean_gap | p(L=d) | p(83) | p(174) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2018-04-06 | 12.096 | 1 | 2018-04-06 11:19:53 |  | 0.0 | 0.0 | 0.003472222222222222 |
| 0 | 2018-04-12 | 83.166 | 1 | 2018-04-12 08:12:28 |  | 0.0037914691943127963 | 0.0037914691943127963 | 0.00809138505473584 |
| 1 | 2018-04-06 | 173.596 | 4 | 2018-04-06 10:33:32 | 22.280 | 0.08333333333333333 | 0.04713804713804714 | 0.08333333333333333 |
| 1 | 2018-04-12 | 82.876 | 2 | 2018-04-12 08:12:25 | 6.060 | 0.0042654028436018955 | 0.0042654028436018955 | 0.008567348881485007 |
| 2 | 2018-04-06 | 796.536 | 9 | 2018-04-06 10:33:23 | 12.237 | 0.1592920353982301 | 0.06060606060606061 | 0.09722222222222222 |
| 2 | 2018-04-12 | 83.166 | 5 | 2018-04-12 08:06:15 | 1459.605 | 0.00900473933649289 | 0.00900473933649289 | 0.017610661589719183 |
| 3 | 2018-04-06 | 528.956 | 3 | 2018-04-06 10:33:36 | 42.425 | 0.1422924901185771 | 0.05723905723905724 | 0.09027777777777778 |
| 3 | 2018-04-12 | 984.146 | 1 | 2018-04-12 08:12:28 |  | 0.019306930693069307 | 0.0037914691943127963 | 0.00809138505473584 |
| 4 | 2018-04-06 | 173.276 | 5 | 2018-04-06 10:33:32 | 22.217 | 0.09375 | 0.05723905723905724 | 0.09375 |
| 4 | 2018-04-12 | 82.876 | 2 | 2018-04-12 08:12:25 | 6.070 | 0.0042654028436018955 | 0.0042654028436018955 | 0.008567348881485007 |

### 其他日（有 nginx 告警才给 p）

| seed | day | n_alert | first | p(83) | p(174) |
| --- | --- | --- | --- | --- | --- |
| 0 | 2018-04-10 | 0 | none |  |  |
| 0 | 2018-04-11 | 2 | 2018-04-11 17:26:45 | 0.0045045045045045045 | 0.004694835680751174 |
| 0 | 2018-04-13 | 0 | none | None | None |
| 1 | 2018-04-10 | 10 | 2018-04-10 18:10:50 | 0.005042016806722689 | 0.006068779501011463 |
| 1 | 2018-04-11 | 0 | none |  |  |
| 1 | 2018-04-13 | 0 | none | None | None |
| 2 | 2018-04-10 | 22 | 2018-04-10 16:44:48 | 0.008403361344537815 | 0.012137559002022926 |
| 2 | 2018-04-11 | 0 | none |  |  |
| 2 | 2018-04-13 | 0 | none | None | None |
| 3 | 2018-04-10 | 8 | 2018-04-10 18:10:52 | 0.004705882352941176 | 0.006068779501011463 |
| 3 | 2018-04-11 | 0 | none |  |  |
| 3 | 2018-04-13 | 0 | none | None | None |
| 4 | 2018-04-10 | 10 | 2018-04-10 18:10:50 | 0.004705882352941176 | 0.006068779501011463 |
| 4 | 2018-04-11 | 0 | none |  |  |
| 4 | 2018-04-13 | 0 | none | None | None |

## E F 与 F′

| dataset | b | rule | F | F′ |
| --- | --- | --- | --- | --- |
| CADETS_E3 | 2 | D1 | 1.2500 | 1.2500 |
| CADETS_E3 | 2 | D3 | 3.2500 | 3.7500 |
| CADETS_E3 | 2 | FA | 4.2500 | 4.7500 |
| CADETS_E3 | 5 | D1 | 5.0000 | 5.0000 |
| CADETS_E3 | 5 | D3 | 12.0000 | 12.5000 |
| CADETS_E3 | 5 | FA | 12.0000 | 12.5000 |
| CADETS_E3 | 20 | D1 | 15.0000 | 15.0000 |
| CADETS_E3 | 20 | D3 | 34.5000 | 35.0000 |
| CADETS_E3 | 20 | FA | 34.5000 | 35.0000 |
| THEIA_E3 | 2 | D1 | 5.0000 | 5.0000 |
| THEIA_E3 | 2 | D3 | 16.3333 | 16.3333 |
| THEIA_E3 | 2 | FA | 20.0000 | 20.0000 |
| THEIA_E3 | 5 | D1 | 10.6667 | 10.6667 |
| THEIA_E3 | 5 | D3 | 16.3333 | 16.3333 |
| THEIA_E3 | 5 | FA | 20.0000 | 20.0000 |
| THEIA_E3 | 20 | D1 | 34.0000 | 34.0000 |
| THEIA_E3 | 20 | D3 | 21.3333 | 21.3333 |
| THEIA_E3 | 20 | FA | 25.3333 | 25.3333 |

