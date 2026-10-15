# PERSIST_three_scorers

探索性。CADETS 15 cell × 三 scorer，事件按 position 对齐。**不改规则/判定。** 已核实。

- 档：VELOX `q99_type`（v9-3 选定）；Kairos `q99_kind`（v9-5 C1）；ORTHRUS `q99_kind`（v9-8 C1）。已核实。
- 自检：gold 信号 45 条，ok=True，flags=0。VELOX 非恒定键 19。已核实。

## 一句话结论

- **A 持续性**：全流 Δ>0 中位 VELOX 0.1912、Kairos 0.0833、ORTHRUS 0.0909；最长正游程中位 2.0/1.0/1.0；max W/h3(5) 中位 0.2849/0.0023/0.0897。 持续性差异存在：VELOX 正增量更密、W 相对阈值更高；历史 scorer 更碎。已核实。
- **A 随重复**：≥3 次键 Spearman 负相关占比 VELOX 0.2857、Kairos 0.4286、ORTHRUS 0.4286；中位 ρ 0.0135/0.0500/0.0000。 中位 ρ≈0，未见系统性随 k 回落（Kairos 从 k=1 就偏低）。已核实。
- **A 邻居污染**：Kairos 平均 u 在 m=0→6–10 为 42.4981→38.1232，ORTHRUS 66.4485→60.0264。 高 m_t 桶略低于 m=0，但是非单调（峰值在 1–2）。已核实。

## A1 持续性（中位数，跨 cell×恶意 process）

### 窗口内该 process 全事件流

| 量             | VELOX 中位 | VELOX 均值 | Kairos 中位 | Kairos 均值 | ORTHRUS 中位 | ORTHRUS 均值 |
| ------------- | -------- | -------- | --------- | --------- | ---------- | ---------- |
| frac_pos      | 0.1912   | 0.2783   | 0.0833    | 0.1550    | 0.0909     | 0.1555     |
| longest_run   | 2.00     | 2.11     | 1.00      | 1.25      | 1.00       | 1.65       |
| mean_run      | 1.40     | 1.37     | 1.00      | 0.94      | 1.00       | 1.08       |
| mean_d_over_c | -0.0219  | -0.0295  | -0.0655   | -0.2748   | -0.0093    | -0.0474    |
| max_W_over_h3 | 0.2849   | 0.3592   | 0.0023    | 0.0283    | 0.0897     | 0.1335     |
| n_rows        | 175      |          | 175       |           | 175        |            |

### 仅该 process 的 M_i 子序列

| 量             | VELOX 中位 | VELOX 均值 | Kairos 中位 | Kairos 均值 | ORTHRUS 中位 | ORTHRUS 均值 |
| ------------- | -------- | -------- | --------- | --------- | ---------- | ---------- |
| frac_pos      | 0.4286   | 0.4003   | 0.2500    | 0.2434    | 0.3333     | 0.2559     |
| longest_run   | 1.00     | 1.40     | 1.00      | 0.86      | 1.00       | 1.05       |
| mean_run      | 1.00     | 1.13     | 1.00      | 0.74      | 1.00       | 0.88       |
| mean_d_over_c | 0.1295   | 0.1196   | -0.0588   | -0.2255   | 0.0533     | 0.0602     |
| max_W_over_h3 | 0.2845   | 0.3508   | 0.0007    | 0.0209    | 0.0929     | 0.1320     |
| n_rows        | 155      |          | 155       |           | 155        |            |

## A2 随重复回落（M_i 中出现 ≥3 次的行为键）

平均 u（百分位 0–100）

| k 桶  | VELOX   | Kairos  | ORTHRUS |
| ---- | ------- | ------- | ------- |
| 1    | 76.7845 | 48.4496 | 64.5235 |
| 2    | 78.0339 | 46.1336 | 59.0046 |
| 3    | 78.8283 | 48.0994 | 66.8358 |
| 4-5  | 64.0671 | 44.7475 | 67.9033 |
| 6-10 |         |         |         |
| >10  |         |         |         |

M_i 中无 k≥6 的键，故 6–10、>10 为空。已核实。

Spearman(k, u)

| scorer  | n_keys | frac_neg | median ρ | mean ρ |
| ------- | ------ | -------- | -------- | ------ |
| velox   | 7      | 0.2857   | 0.0135   | 0.2545 |
| kairos  | 7      | 0.4286   | 0.0500   | 0.0142 |
| orthrus | 7      | 0.4286   | 0.0000   | 0.0042 |

### VELOX 自检：分数不恒定的键

共 19 个（列出前 20）。已核实。

| seed | attack            | key                            | n | n_s | n_triples | reason                            |
| ---- | ----------------- | ------------------------------ | - | --- | --------- | --------------------------------- |
| 0    | Nginx_Backdoor_06 | vugefal|netflow:26318|SENDTO   | 3 | 3   | 1         | same triple, score not constant   |
| 0    | Nginx_Backdoor_06 | vugefal|netflow:26318|RECVFROM | 3 | 3   | 1         | same triple, score not constant   |
| 0    | Nginx_Backdoor_12 | nginx|netflow:140960|SENDTO    | 3 | 2   | 1         | same triple, score not constant   |
| 0    | Nginx_Backdoor_12 | sendmail|subject:379506|OPEN   | 4 | 2   | 4         | different (src,dst,etype) triples |
| 1    | Nginx_Backdoor_06 | vugefal|netflow:26318|SENDTO   | 3 | 3   | 1         | same triple, score not constant   |
| 1    | Nginx_Backdoor_06 | vugefal|netflow:26318|RECVFROM | 3 | 3   | 1         | same triple, score not constant   |
| 1    | Nginx_Backdoor_12 | nginx|netflow:140960|SENDTO    | 3 | 2   | 1         | same triple, score not constant   |
| 1    | Nginx_Backdoor_12 | sendmail|subject:379506|OPEN   | 4 | 2   | 4         | different (src,dst,etype) triples |
| 2    | Nginx_Backdoor_06 | vugefal|netflow:26318|SENDTO   | 3 | 3   | 1         | same triple, score not constant   |
| 2    | Nginx_Backdoor_06 | vugefal|netflow:26318|RECVFROM | 3 | 3   | 1         | same triple, score not constant   |
| 2    | Nginx_Backdoor_12 | nginx|netflow:140960|SENDTO    | 3 | 2   | 1         | same triple, score not constant   |
| 2    | Nginx_Backdoor_12 | sendmail|subject:379506|OPEN   | 4 | 2   | 4         | different (src,dst,etype) triples |
| 3    | Nginx_Backdoor_06 | vugefal|netflow:26318|SENDTO   | 3 | 3   | 1         | same triple, score not constant   |
| 3    | Nginx_Backdoor_06 | vugefal|netflow:26318|RECVFROM | 3 | 3   | 1         | same triple, score not constant   |
| 3    | Nginx_Backdoor_12 | nginx|netflow:140960|SENDTO    | 3 | 2   | 1         | same triple, score not constant   |
| 3    | Nginx_Backdoor_12 | sendmail|subject:379506|OPEN   | 4 | 2   | 4         | different (src,dst,etype) triples |
| 4    | Nginx_Backdoor_06 | vugefal|netflow:26318|SENDTO   | 3 | 3   | 1         | same triple, score not constant   |
| 4    | Nginx_Backdoor_06 | vugefal|netflow:26318|RECVFROM | 3 | 3   | 1         | same triple, score not constant   |
| 4    | Nginx_Backdoor_12 | nginx|netflow:140960|SENDTO    | 3 | 2   | 1         | same triple, score not constant   |

## A2 对照（验证日、同程序名的 benign 键）

| k 桶  | VELOX   | Kairos  | ORTHRUS |
| ---- | ------- | ------- | ------- |
| 1    | 50.0817 | 42.6107 | 49.9526 |
| 2    | 50.6991 | 42.4441 | 50.3598 |
| 3    | 50.2505 | 43.0524 | 49.9833 |
| 4-5  | 50.5038 | 43.3612 | 49.4573 |
| 6-10 | 52.3076 | 42.4718 | 51.6056 |
| >10  | 57.0955 | 50.0197 | 58.7835 |

Spearman 对照

| scorer  | n_keys | frac_neg | median ρ |
| ------- | ------ | -------- | -------- |
| velox   | 77     | 0.4935   | 0.0045   |
| kairos  | 77     | 0.5065   | -0.0009  |
| orthrus | 77     | 0.6104   | -0.0227  |

## A3 邻居污染（执行 process 前 20 个事件中的 M_i 数）

| m_t 桶 | Kairos mean u | n   | ORTHRUS mean u | n   |
| ----- | ------------- | --- | -------------- | --- |
| 0     | 42.4981       | 180 | 66.4485        | 180 |
| 1-2   | 51.7153       | 245 | 73.9587        | 245 |
| 3-5   | 50.7816       | 140 | 68.1965        | 140 |
| 6-10  | 38.1232       | 155 | 60.0264        | 155 |
| >10   | 45.3837       | 25  | 58.6825        | 25  |

## A4 每个 cell 上 u 最高的 3 个恶意事件是该键第几次

| scorer  | median k of top-1 | mean k top-1 | median k top-3 | frac k=1 among top-1 |
| ------- | ----------------- | ------------ | -------------- | -------------------- |
| velox   | 1.00              | 1.33         | 1.00           | 0.8000               |
| kairos  | 1.00              | 1.40         | 1.00           | 0.6667               |
| orthrus | 1.00              | 1.27         | 1.00           | 0.8667               |

