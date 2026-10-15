# THEIA_diag

探索性。THEIA × VELOX v9-3 选定档 `q99_kind`，10 cell。**不改规则/判定。** 已核实。

- 自检：10 条 t*/通道 vs per_cell/eval，ok=True，flags=0。已核实。

## 一句话结论

- **信号**：M_i 上 s>δ 中位 0.1676，ΣΔ 均 >0（非零信号）。max W/h3(5) 中位 0.8161，≥1 的 cell 5/10（Firefox 1/5，dropper 4/5）。卡点主要在积累/阈值，不是“完全没分数”。已核实。
- **证据预算 / 阈值分辨率**：退化 seed1 的 h1(0)=25.9，测试日 D1@0 标记 0 个进程；h3(5)/c=7.000，其余 seed 中 3/4 的 h3(5)=2c（cap 平台）。已核实。
- **通道 / transfer**：FA 6/10（Firefox 2/5、dropper 4/5；D1 3、D3 3）。测试日越过 h3 的 benign 里，firefox/fluxbox 常不在验证日（in_val=0），验证日顶格多为 bash/dash。主因是阈值分辨率+验证日程序与测试日 transfer 错位，其次是入口 process 被大量 benign 稀释。已核实。

## B1 证据预算

| seed | h1(0)   | c      | h2(5)   | h3(0)   | h3(1)   | h3(2)   | h3(5)   | h3(10)  | h3(20)  | h3(50)  | h3(5)/c | n_proc_val |
| ---- | ------- | ------ | ------- | ------- | ------- | ------- | ------- | ------- | ------- | ------- | ------- | ---------- |
| 0    | 11.5121 | 3.8809 | 7.7618  | 9.3006  | 8.3931  | 7.9497  | 7.7618  | 7.7618  | 7.7618  | 7.7618  | 2.000   | 12055      |
| 1    | 25.9038 | 4.3111 | 30.1779 | 31.8373 | 31.8373 | 31.8373 | 30.1779 | 30.1779 | 30.1779 | 23.6031 | 7.000   | 12055      |
| 2    | 15.5291 | 3.9076 | 7.8152  | 9.4945  | 9.3058  | 8.2984  | 7.8152  | 7.8152  | 7.8152  | 7.8152  | 2.000   | 12055      |
| 3    | 8.5007  | 6.6872 | 12.0118 | 12.0118 | 12.0118 | 12.0118 | 12.0118 | 12.0118 | 12.0118 | 10.7608 | 1.796   | 12055      |
| 4    | 8.7094  | 3.3399 | 6.6798  | 6.6798  | 6.6798  | 6.6798  | 6.6798  | 6.6798  | 6.6798  | 6.6798  | 2.000   | 12055      |

验证日每 process 最大 W 前 25（每 seed）

| seed | rank | proc   | program     | max_W   |
| ---- | ---- | ------ | ----------- | ------- |
| 0    | 1    | 336211 | bash        | 9.1773  |
| 0    | 2    | 333636 | bash        | 8.3931  |
| 0    | 3    | 340370 | bash        | 7.9497  |
| 0    | 4    | 331239 | bash        | 7.7618  |
| 0    | 5    | 331347 | bash        | 7.7618  |
| 0    | 6    | 331571 | bash        | 7.7618  |
| 0    | 7    | 331870 | bash        | 7.7618  |
| 0    | 8    | 332074 | bash        | 7.7618  |
| 0    | 9    | 332299 | bash        | 7.7618  |
| 0    | 10   | 332504 | bash        | 7.7618  |
| 0    | 11   | 332759 | bash        | 7.7618  |
| 0    | 12   | 332988 | bash        | 7.7618  |
| 0    | 13   | 333241 | bash        | 7.7618  |
| 0    | 14   | 333401 | bash        | 7.7618  |
| 0    | 15   | 333576 | bash        | 7.7618  |
| 0    | 16   | 334059 | bash        | 7.7618  |
| 0    | 17   | 334545 | bash        | 7.7618  |
| 0    | 18   | 334985 | bash        | 7.7618  |
| 0    | 19   | 335047 | bash        | 7.7618  |
| 0    | 20   | 335265 | bash        | 7.7618  |
| 0    | 21   | 335617 | bash        | 7.7618  |
| 0    | 22   | 335755 | bash        | 7.7618  |
| 0    | 23   | 335847 | bash        | 7.7618  |
| 0    | 24   | 336055 | bash        | 7.7618  |
| 0    | 25   | 336545 | bash        | 7.7618  |
| 1    | 1    | 334404 | dash        | 31.8373 |
| 1    | 2    | 338589 | dash        | 31.8373 |
| 1    | 3    | 340460 | dash        | 31.8373 |
| 1    | 4    | 340275 | dash        | 30.4332 |
| 1    | 5    | 331430 | dash        | 30.1779 |
| 1    | 6    | 331933 | dash        | 30.1779 |
| 1    | 7    | 332158 | dash        | 30.1779 |
| 1    | 8    | 332363 | dash        | 30.1779 |
| 1    | 9    | 332521 | dash        | 30.1779 |
| 1    | 10   | 332618 | dash        | 30.1779 |
| 1    | 11   | 333100 | dash        | 30.1779 |
| 1    | 12   | 333260 | dash        | 30.1779 |
| 1    | 13   | 333479 | dash        | 30.1779 |
| 1    | 14   | 333656 | dash        | 30.1779 |
| 1    | 15   | 333914 | dash        | 30.1779 |
| 1    | 16   | 334106 | dash        | 30.1779 |
| 1    | 17   | 335124 | dash        | 30.1779 |
| 1    | 18   | 335334 | dash        | 30.1779 |
| 1    | 19   | 335476 | dash        | 30.1779 |
| 1    | 20   | 336609 | dash        | 30.1779 |
| 1    | 21   | 336891 | dash        | 30.1779 |
| 1    | 22   | 336993 | dash        | 30.1779 |
| 1    | 23   | 337235 | dash        | 30.1779 |
| 1    | 24   | 337381 | dash        | 30.1779 |
| 1    | 25   | 337539 | dash        | 30.1779 |
| 2    | 1    | 336206 | dhclient    | 8.5952  |
| 2    | 2    | 331032 | thunderbird | 8.1379  |
| 2    | 3    | 336211 | bash        | 7.9509  |
| 2    | 4    | 331239 | bash        | 7.8152  |
| 2    | 5    | 331347 | bash        | 7.8152  |
| 2    | 6    | 331571 | bash        | 7.8152  |
| 2    | 7    | 331870 | bash        | 7.8152  |
| 2    | 8    | 332074 | bash        | 7.8152  |
| 2    | 9    | 332299 | bash        | 7.8152  |
| 2    | 10   | 332504 | bash        | 7.8152  |
| 2    | 11   | 332759 | bash        | 7.8152  |
| 2    | 12   | 332988 | bash        | 7.8152  |
| 2    | 13   | 333241 | bash        | 7.8152  |
| 2    | 14   | 333401 | bash        | 7.8152  |
| 2    | 15   | 333576 | bash        | 7.8152  |
| 2    | 16   | 334059 | bash        | 7.8152  |
| 2    | 17   | 334545 | bash        | 7.8152  |
| 2    | 18   | 334985 | bash        | 7.8152  |
| 2    | 19   | 335047 | bash        | 7.8152  |
| 2    | 20   | 335265 | bash        | 7.8152  |
| 2    | 21   | 335617 | bash        | 7.8152  |
| 2    | 22   | 335755 | bash        | 7.8152  |
| 2    | 23   | 335847 | bash        | 7.8152  |
| 2    | 24   | 336055 | bash        | 7.8152  |
| 2    | 25   | 336545 | bash        | 7.8152  |
| 3    | 1    | 335755 | bash        | 12.0118 |
| 3    | 2    | 335847 | bash        | 12.0118 |
| 3    | 3    | 332988 | bash        | 12.0118 |
| 3    | 4    | 331239 | bash        | 12.0118 |
| 3    | 5    | 334545 | bash        | 12.0118 |
| 3    | 6    | 336055 | bash        | 12.0118 |
| 3    | 7    | 336545 | bash        | 12.0118 |
| 3    | 8    | 338101 | bash        | 12.0118 |
| 3    | 9    | 338261 | bash        | 12.0118 |
| 3    | 10   | 338730 | bash        | 12.0118 |
| 3    | 11   | 340601 | bash        | 12.0118 |
| 3    | 12   | 340807 | bash        | 12.0118 |
| 3    | 13   | 342104 | bash        | 12.0118 |
| 3    | 14   | 343582 | bash        | 12.0118 |
| 3    | 15   | 343843 | bash        | 12.0118 |
| 3    | 16   | 331870 | bash        | 12.0118 |
| 3    | 17   | 339023 | bash        | 12.0118 |
| 3    | 18   | 344387 | bash        | 12.0118 |
| 3    | 19   | 344446 | bash        | 12.0118 |
| 3    | 20   | 334985 | bash        | 12.0118 |
| 3    | 21   | 335047 | bash        | 12.0118 |
| 3    | 22   | 331240 | dash        | 11.3300 |
| 3    | 23   | 331178 | run-parts   | 10.8064 |
| 3    | 24   | 334925 | run-parts   | 10.8064 |
| 3    | 25   | 343522 | run-parts   | 10.8064 |
| 4    | 1    | 331239 | bash        | 6.6798  |
| 4    | 2    | 331347 | bash        | 6.6798  |
| 4    | 3    | 331571 | bash        | 6.6798  |
| 4    | 4    | 331870 | bash        | 6.6798  |
| 4    | 5    | 332074 | bash        | 6.6798  |
| 4    | 6    | 332299 | bash        | 6.6798  |
| 4    | 7    | 332504 | bash        | 6.6798  |
| 4    | 8    | 332759 | bash        | 6.6798  |
| 4    | 9    | 332988 | bash        | 6.6798  |
| 4    | 10   | 333241 | bash        | 6.6798  |
| 4    | 11   | 333401 | bash        | 6.6798  |
| 4    | 12   | 333576 | bash        | 6.6798  |
| 4    | 13   | 334059 | bash        | 6.6798  |
| 4    | 14   | 334545 | bash        | 6.6798  |
| 4    | 15   | 334985 | bash        | 6.6798  |
| 4    | 16   | 335047 | bash        | 6.6798  |
| 4    | 17   | 335265 | bash        | 6.6798  |
| 4    | 18   | 335617 | bash        | 6.6798  |
| 4    | 19   | 335755 | bash        | 6.6798  |
| 4    | 20   | 335847 | bash        | 6.6798  |
| 4    | 21   | 336055 | bash        | 6.6798  |
| 4    | 22   | 336205 | dhclient    | 6.6798  |
| 4    | 23   | 336545 | bash        | 6.6798  |
| 4    | 24   | 336851 | bash        | 6.6798  |
| 4    | 25   | 337134 | bash        | 6.6798  |

## B2 恶意事件信号

| seed | attack                            | s>δ    | ΣΔ      | maxW/h3 | proc   | FA ch | D1@0 | idx0   | D1@5 | idx5   |
| ---- | --------------------------------- | ------ | ------- | ------- | ------ | ----- | ---- | ------ | ---- | ------ |
| 0    | Firefox_Backdoor_Drakon_In_Memory | 0.5838 | 32.057  | 0.5000  | 282484 | D1    | 1    | 131381 | 1    | 131381 |
| 0    | Browser_Extension_Drakon_Dropper  | 0.4679 | 63.401  | 1.4431  | 216310 | D3    | 1    | 855262 | 1    | 797113 |
| 1    | Firefox_Backdoor_Drakon_In_Memory | 0.1561 | 21.857  | 0.1429  | 282590 | miss  | 0    |        | 0    |        |
| 1    | Browser_Extension_Drakon_Dropper  | 0.1154 | 61.892  | 0.5497  | 216310 | miss  | 0    |        | 0    |        |
| 2    | Firefox_Backdoor_Drakon_In_Memory | 0.1618 | 19.624  | 1.0825  | 282484 | D3    | 0    |        | 0    |        |
| 2    | Browser_Extension_Drakon_Dropper  | 0.1538 | 50.234  | 1.5000  | 216933 | D3    | 0    |        | 1    | 812430 |
| 3    | Firefox_Backdoor_Drakon_In_Memory | 0.2543 | 21.194  | 0.4425  | 284530 | miss  | 0    |        | 0    |        |
| 3    | Browser_Extension_Drakon_Dropper  | 0.2885 | 122.832 | 1.5319  | 216310 | D1    | 1    | 797113 | 1    | 797113 |
| 4    | Firefox_Backdoor_Drakon_In_Memory | 0.1734 | 18.603  | 0.5000  | 282590 | miss  | 0    |        | 0    |        |
| 4    | Browser_Extension_Drakon_Dropper  | 0.1603 | 44.102  | 1.1592  | 216310 | D1    | 1    | 797113 | 1    | 797113 |

## B3 入口 process（first_Mi + 同窗口 firefox/dash）

| seed | attack                            | day        | role     | proc   | program | n_ben | n_mal | n_pre | W/h @ t0 |
| ---- | --------------------------------- | ---------- | -------- | ------ | ------- | ----- | ----- | ----- | -------- |
| 0    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | first_Mi | 282484 | fluxbox | 1067  | 25    | 0     | 0.0000   |
| 0    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | firefox  | 282560 | firefox | 2     | 14    | 0     | 0.0000   |
| 0    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | fluxbox  | 284406 | fluxbox | 2477  | 42    | 0     | 0.0000   |
| 0    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | first_Mi | 216082 | firefox | 8     | 6     | 0     | 0.0000   |
| 0    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | firefox  | 216308 | firefox | 8     | 10    | 0     | 0.0000   |
| 0    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | dash     | 216310 | dash    | 7     | 39    | 0     | 0.0000   |
| 1    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | first_Mi | 282484 | fluxbox | 1067  | 25    | 0     | 0.0000   |
| 1    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | firefox  | 282560 | firefox | 2     | 14    | 0     | 0.0000   |
| 1    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | fluxbox  | 284406 | fluxbox | 2477  | 42    | 0     | 0.0000   |
| 1    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | first_Mi | 216082 | firefox | 8     | 6     | 0     | 0.0000   |
| 1    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | firefox  | 216308 | firefox | 8     | 10    | 0     | 0.0000   |
| 1    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | dash     | 216310 | dash    | 7     | 39    | 0     | 0.0000   |
| 2    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | first_Mi | 282484 | fluxbox | 1067  | 25    | 0     | 0.0000   |
| 2    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | firefox  | 282560 | firefox | 2     | 14    | 0     | 0.0000   |
| 2    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | fluxbox  | 284406 | fluxbox | 2477  | 42    | 0     | 0.0000   |
| 2    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | first_Mi | 216082 | firefox | 8     | 6     | 0     | 0.0000   |
| 2    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | firefox  | 216308 | firefox | 8     | 10    | 0     | 0.0000   |
| 2    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | dash     | 216310 | dash    | 7     | 39    | 0     | 0.0000   |
| 3    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | first_Mi | 282484 | fluxbox | 1067  | 25    | 0     | 0.0000   |
| 3    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | firefox  | 282560 | firefox | 2     | 14    | 0     | 0.0000   |
| 3    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | fluxbox  | 284406 | fluxbox | 2477  | 42    | 0     | 0.0000   |
| 3    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | first_Mi | 216082 | firefox | 8     | 6     | 0     | 0.0000   |
| 3    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | firefox  | 216308 | firefox | 8     | 10    | 0     | 0.0000   |
| 3    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | dash     | 216310 | dash    | 7     | 39    | 0     | 0.0000   |
| 4    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | first_Mi | 282484 | fluxbox | 1067  | 25    | 0     | 0.0000   |
| 4    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | firefox  | 282560 | firefox | 2     | 14    | 0     | 0.0000   |
| 4    | Firefox_Backdoor_Drakon_In_Memory | 2018-04-10 | fluxbox  | 284406 | fluxbox | 2477  | 42    | 0     | 0.0000   |
| 4    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | first_Mi | 216082 | firefox | 8     | 6     | 0     | 0.0000   |
| 4    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | firefox  | 216308 | firefox | 8     | 10    | 0     | 0.0000   |
| 4    | Browser_Extension_Drakon_Dropper  | 2018-04-12 | dash     | 216310 | dash    | 7     | 39    | 0     | 0.0000   |

## B4 transfer（测试日越过 h3(5) 的 benign process，按程序名）

### seed0

| program             | n_alerts | in_val |
| ------------------- | -------- | ------ |
| firefox             | 365      | 0      |
| bash                | 188      | 1      |
| dash                | 31       | 1      |
| console-kit-daemon  | 7        | 1      |
| dhclient            | 4        | 1      |
| gvfsd               | 4        | 0      |
| thunderbird         | 4        | 1      |
| unity-panel-service | 4        | 0      |
| gconfd              | 2        | 0      |
| accounts-daemon     | 1        | 0      |

### seed1

| program | n_alerts | in_val |
| ------- | -------- | ------ |
| bash    | 14       | 1      |
| dash    | 10       | 1      |

### seed2

| program           | n_alerts | in_val |
| ----------------- | -------- | ------ |
| fluxbox           | 2185     | 0      |
| firefox           | 896      | 0      |
| bash              | 551      | 1      |
| pulseaudio        | 231      | 0      |
| thunderbird       | 42       | 1      |
| postgres          | 28       | 1      |
| crashreporter     | 21       | 0      |
| dhclient          | 15       | 1      |
| unity-2d-panel    | 8        | 0      |
| gnome-screensaver | 4        | 0      |

### seed3

| program             | n_alerts | in_val |
| ------------------- | -------- | ------ |
| bash                | 46       | 1      |
| fluxbox             | 28       | 0      |
| postgres            | 18       | 1      |
| python              | 7        | 1      |
| dhclient            | 5        | 1      |
| dash                | 2        | 1      |
| firefox             | 2        | 0      |
| gnome-terminal      | 1        | 0      |
| unity-panel-service | 1        | 0      |

### seed4

| program                    | n_alerts | in_val |
| -------------------------- | -------- | ------ |
| bash                       | 47       | 1      |
| fluxbox                    | 47       | 0      |
| firefox                    | 46       | 0      |
| dash                       | 8        | 1      |
| dhclient                   | 8        | 1      |
| gnome-terminal             | 2        | 0      |
| init                       | 2        | 1      |
| indicator-printers-service | 1        | 0      |
| python                     | 1        | 1      |
| unity-panel-service        | 1        | 0      |

## B5 退化 seed

- 退化 seed：**1**。h1(0)=25.9038。测试日 D1@0 标记进程数=0。已核实。
- who_d1 顶格程序：dash#331430=25.9, dash#331933=25.9, dash#332158=25.9, dash#332363=25.9, dash#332521=25.9。已核实。
- 原因（已核实）：h1(0)=nextafter(验证日最大 process 分数)；seed1 上多个 `dash` 打到同一 max，预算 0–10 的 h1 几乎相同；测试日没有 process 超过该 max，故 D1@0 不标记任何节点。
- 各 seed 测试日 D1@0 标记进程数：{0: 15, 1: 0, 2: 8, 3: 23, 4: 22}。已核实。

