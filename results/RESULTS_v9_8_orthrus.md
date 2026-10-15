# RESULTS_v9_8_orthrus

scorer=ORTHRUS epoch 11 edge_losses；rearm=reset；P1；预算 {0,1,2,5,10,20,50}；CADETS_E3 seed 0–4。THEIA 不跑。
信号判据引用 v9-7：seed 0/3/4 标记到 ≥1 个 GT 节点，3/5，signal 成立。本阶段不重新判定。

## 判定

- C1 选中组合：`q99_kind`（C1 未通过）。类别：**no-gain-with-signal**。
- 预注册：E_FA(b=5)−E_D1(b=5) ≥ 0.1 且 F_FA(b=5) ≤ F_D1(b=20)。C1：ΔE=-0.0861，F_FA=23.2500，F_D1@20=41.5000 → no-gain。
- q99+type：ΔE=0.0060，F_FA=24.7500，F_D1@20=41.5000 → no-gain。
- 固定句（C1）：With ORTHRUS's per-event scores, which separate the attacks (the event-level rule detects 5 of the 15 pairs at $b=5$), FirstAlarm adds no gain (0.0820 against 0.1682), so the gain is shown only with VELOX's scores.
- 固定句（q99+type 同一判定）：With ORTHRUS's per-event scores, which separate the attacks (the event-level rule detects 5 of the 15 pairs at $b=5$), FirstAlarm adds no gain (0.1741 against 0.1682), so the gain is shown only with VELOX's scores.
- 前置检查 ok=True；自检 ok=False。
- D1@b=5 hits=5/15；FA@b=5 hits=3/15。
- 自检 flags 不改判定：pipeline failure 仅当前置检查失败或重放出错。

## 前置检查

- 预注册自 2913926546ea2c886d47667ad9df689515ad21db 起 diff 空=True。
- seed 隔离：training 互异=True；同名窗口两两 md5 冲突=[]。
- 10× 尺度标记（不剔除）：[]

## 分解量 FA@b=5

- vs D1@b=5：{'both': 3, 'fa_only': 0, 'd1_only': 2, 'none': 10, 'mean_rho_fa_only': None, 'mean_rho_d1_only': 0.3541666666666667, 'mean_rho_both_fa': 0.589781746031746, 'mean_rho_both_d1': 0.589781746031746, 'mean_rho_fa_detected': 0.589781746031746, 'mean_rho_d1_detected': 0.49553571428571425}
- vs D1@b=20：{'both': 3, 'fa_only': 0, 'd1_only': 10, 'none': 2, 'mean_rho_fa_only': None, 'mean_rho_d1_only': 0.5252976190476191, 'mean_rho_both_fa': 0.589781746031746, 'mean_rho_both_d1': 0.589781746031746, 'mean_rho_fa_detected': 0.589781746031746, 'mean_rho_d1_detected': 0.5401785714285714}
- vs D1@b=0：{'both': 3, 'fa_only': 0, 'd1_only': 0, 'none': 12, 'mean_rho_fa_only': None, 'mean_rho_d1_only': None, 'mean_rho_both_fa': 0.589781746031746, 'mean_rho_both_d1': 0.589781746031746, 'mean_rho_fa_detected': 0.589781746031746, 'mean_rho_d1_detected': 0.589781746031746}

## nginx A1/A2（b=5，P_i 中最早越阈；已核实自 standing）

- A1 Nginx_Backdoor_12 day=2018-04-12: first=none proc=None W/h@t0=None n_alert_before_t0=None
  per-seed: seed0=none, seed1=none, seed2=none, seed3=none, seed4=none
- A2 Nginx_Backdoor_13 day=2018-04-13: first=none proc=None W/h@t0=None n_alert_before_t0=None
  per-seed: seed0=none, seed1=none, seed2=2018-04-13 09:19:50, seed3=none, seed4=none

## 自检

- |P_i|/|M_i|：[{'attack': 'Nginx_Backdoor_06', 'day': '2018-04-06', 'P': 2, 'M': 21, 'G': 8}, {'attack': 'Nginx_Backdoor_12', 'day': '2018-04-12', 'P': 24, 'M': 96, 'G': 43}, {'attack': 'Nginx_Backdoor_13', 'day': '2018-04-13', 'P': 14, 'M': 32, 'G': 24}]
- 期望 2/21、24/96、14/32。flags=['seed0 D1 val flagged 9 != b=10', 'seed0 D1 val flagged 9 != b=20', 'seed0 D1 val flagged 47 != b=50', 'seed1 D1 val flagged 8 != b=10', 'seed1 D1 val flagged 20 != b=50', 'seed2 D1 val flagged 47 != b=50', 'seed3 D1 val flagged 1 != b=2', 'seed3 D1 val flagged 4 != b=5', 'seed3 D1 val flagged 4 != b=10', 'seed4 D1 val flagged 14 != b=20']
- 验证日 flagged≠b：calib 用 nextafter(第 b+1 大 process max, +∞)；并列 max 时无法恰为 b（方法未改）。不改阈值、不改判定。
- E from per_cell：table 0.082044 csv 0.082044

## D1 与 FA 全预算 (E, F)

- b=0: D1 E=0.0820 (miss 12) F=0.7500；FA E=0.0820 (miss 12) F=0.7500
- b=1: D1 E=0.1251 (miss 11) F=0.7500；FA E=0.0820 (miss 12) F=1.7500
- b=2: D1 E=0.1682 (miss 10) F=1.7500；FA E=0.0820 (miss 12) F=7.5000
- b=5: D1 E=0.1682 (miss 10) F=4.7500；FA E=0.0820 (miss 12) F=23.2500
- b=10: D1 E=0.2071 (miss 8) F=5.2500；FA E=0.1687 (miss 10) F=59.7500
- b=20: D1 E=0.3985 (miss 2) F=41.5000；FA E=0.4272 (miss 5) F=114.2500
- b=50: D1 E=0.4318 (miss 2) F=81.7500；FA E=0.5587 (miss 4) F=204.2500

## 保真度（轻量）

- 已做轻量对比：D1@b=0 为测试期 process 事件 loss≥h1(0) 的进程集合；PIDSMaker 为 node_evaluation 中 y_pred=1 且类型=process 的节点。两口径阈值不同（h1(0)=验证日最大 process loss 之上；PIDSMaker=max_val_loss），交集/差集如下，不作为判定输入。
- seed0: |D1@b=0|=7 |PM process|=7 ∩=7 only_D1=0 only_PM=0
- seed1: |D1@b=0|=3 |PM process|=3 ∩=3 only_D1=0 only_PM=0
- seed2: |D1@b=0|=2 |PM process|=2 ∩=2 only_D1=0 only_PM=0
- seed3: |D1@b=0|=2 |PM process|=2 ∩=2 only_D1=0 only_PM=0
- seed4: |D1@b=0|=8 |PM process|=8 ∩=8 only_D1=0 only_PM=0

## 重放吞吐

- seed0 q99_kind wall=67.80875934497453s n=1987981 ev/s=29317.466050163534
- seed1 q99_kind wall=65.68250520108268s n=1987981 ev/s=30266.52217228814
- seed2 q99_kind wall=68.39030689117499s n=1987981 ev/s=29068.169019380828
- seed3 q99_kind wall=66.82437664992176s n=1987981 ev/s=29749.33848488548
- seed4 q99_kind wall=70.43600361305289s n=1987981 ev/s=28223.932336098584
- seed0 q99_type wall=67.18451266502962s n=1987981 ev/s=29589.870062937425
- seed1 q99_type wall=65.58219474204816s n=1987981 ev/s=30312.81596810303
- seed2 q99_type wall=68.24053610907868s n=1987981 ev/s=29131.966326031255
- seed3 q99_type wall=67.51612834096886s n=1987981 ev/s=29444.53494075268
- seed4 q99_type wall=70.14351302315481s n=1987981 ev/s=28341.622971517765

