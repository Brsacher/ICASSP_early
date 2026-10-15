# RESULTS_v9_5_kairos

scorer=Kairos epoch 11 edge_losses；rearm=reset；P1；预算 {0,1,2,5,10,20,50}；CADETS_E3 seed 0–4。THEIA 不跑。

## 判定

- C1 选中组合：`q99_kind`（C1 未通过）。类别：**no-gain**。
- 预注册：E_FA(b=5)−E_D1(b=5) ≥ 0.1 且 F_FA(b=5) ≤ F_D1(b=20)。C1：ΔE=-0.0903，F_FA=20.7500，F_D1@20=145.2500 → no-gain。
- q99+type：ΔE=-0.0903，F_FA=24.0000，F_D1@20=145.2500 → no-gain。
- 前置检查 ok=True；自检 ok=True。

## 前置检查

- seed 隔离：training 互异=True；同名窗口两两 md5 冲突=[]。
- 10× 尺度标记（不剔除）：[]

## 分解量 FA@b=5

- vs D1@b=5：{'both': 0, 'fa_only': 0, 'd1_only': 2, 'none': 13, 'mean_rho_fa_only': None, 'mean_rho_d1_only': 0.3229166666666667, 'mean_rho_both_fa': None, 'mean_rho_both_d1': None, 'mean_rho_fa_detected': None, 'mean_rho_d1_detected': 0.3229166666666667}
- vs D1@b=20：{'both': 0, 'fa_only': 0, 'd1_only': 4, 'none': 11, 'mean_rho_fa_only': None, 'mean_rho_d1_only': 0.37760416666666663, 'mean_rho_both_fa': None, 'mean_rho_both_d1': None, 'mean_rho_fa_detected': None, 'mean_rho_d1_detected': 0.37760416666666663}

## nginx A1/A2（b=5，P_i 中最早越阈；已核实自 standing）

- A1 Nginx_Backdoor_12 day=2018-04-12：仅 seed3 越阈 first=2018-04-12 03:01:13 proc=336472 W/h@t0=0.3093 n_alert_before_t0=1；seed 0/1/2/4 为 none。
- A2 Nginx_Backdoor_13 day=2018-04-13：五 seed 均 none（t0 前告警次数皆 0）。

## 自检

- |P_i|/|M_i|：[{'attack': 'Nginx_Backdoor_06', 'day': '2018-04-06', 'P': 2, 'M': 21, 'G': 8}, {'attack': 'Nginx_Backdoor_12', 'day': '2018-04-12', 'P': 24, 'M': 96, 'G': 43}, {'attack': 'Nginx_Backdoor_13', 'day': '2018-04-13', 'P': 14, 'M': 32, 'G': 24}]
- 期望 2/21、24/96、14/32。flags=[]
- E from per_cell：table 0.000000 csv 0.000000

## 保真度（可选）

- 未做：result_model_epoch_11.pth 不是与 D1@b=0 同口径的 process 集合，无法机械逐 seed 对齐

## 重放吞吐

- seed0 q99_kind wall=69.64928023889661s n=1987981 ev/s=28542.735735117967
- seed1 q99_kind wall=69.35439073597081s n=1987981 ev/s=28664.09723889232
- seed2 q99_kind wall=69.48995190812275s n=1987981 ev/s=28608.179246237512
- seed3 q99_kind wall=69.64557502511889s n=1987981 ev/s=28544.254237013625
- seed4 q99_kind wall=69.29812118900008s n=1987981 ev/s=28687.372267685067
- seed0 q99_type wall=69.62128191092052s n=1987981 ev/s=28554.21424936695
- seed1 q99_type wall=70.30924206599593s n=1987981 ev/s=28274.817670968165
- seed2 q99_type wall=76.51595251215622s n=1987981 ev/s=25981.261877177392
- seed3 q99_type wall=67.64667875901796s n=1987981 ev/s=29387.710327685272
- seed4 q99_type wall=66.32307758904062s n=1987981 ev/s=29974.1971010178

