# TABLE1_reset_q99_kind

## quiet-start

| dataset | attack | b | D1 ρ (k/5) | D1 d | D1 FP | D2 ρ (k/5) | D2 d | D2 FP | D3 ρ (k/5) | D3 d | D3 FP | FirstAlarm ρ (k/5) | FirstAlarm d | FirstAlarm FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CADETS_E3 | Nginx_Backdoor_06 | 2 | 0.24 (2/5) | 271 | 2 | miss (0/5) | miss | 2 | 1.00 (1/5) | 2692 | 2 | **0.43 (3/5)** | **529** | 3 |
| CADETS_E3 | Nginx_Backdoor_06 | 5 | 0.24 (2/5) | 271 | 6 | 0.48 (4/5) | 621 | 15 | 0.67 (5/5) | 797 | 14 | **0.43 (5/5)** | **529** | 14 |
| CADETS_E3 | Nginx_Backdoor_12 | 2 | **0.28 (4/5)** | **254** | 2 | miss (0/5) | miss | 3 | miss (0/5) | miss | 4 | **0.28 (4/5)** | **254** | 5 |
| CADETS_E3 | Nginx_Backdoor_12 | 5 | 0.28 (4/5) | 254 | 5 | 0.12 (3/5) | 83 | 6 | 0.12 (3/5) | 83 | 5 | **0.28 (5/5)** | **254** | 6 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 2 | 0.31 (1/5) | 330 | 2 | 0.00† (1/5) | 32 | 7 | 0.00† (1/5) | 32 | 9 | **0.16† (2/5)** | **181** | 9 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 5 | 0.31 (1/5) | 330 | 7 | 0.00† (1/5) | 32 | 7 | 0.00† (1/5) | 32 | 9 | **0.16† (2/5)** | **181** | 9 |

## spike-start

| dataset | attack | b | D1 ρ (k/5) | D1 d | D1 FP | D2 ρ (k/5) | D2 d | D2 FP | D3 ρ (k/5) | D3 d | D3 FP | FirstAlarm ρ (k/5) | FirstAlarm d | FirstAlarm FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CADETS_E3 | Nginx_Backdoor_13 | 2 | **0.05 (2/5)** | **111** | 0 | miss (0/5) | miss | 1 | miss (0/5) | miss | 1 | 0.06 (2/5) | 111 | 1 |
| CADETS_E3 | Nginx_Backdoor_13 | 5 | **0.06 (3/5)** | **111** | 2 | 0.34 (1/5) | 251 | 2 | 0.34 (1/5) | 251 | 2 | **0.06 (3/5)** | **111** | 2 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 2 | **0.01 (4/5)** | **2** | 10 | 0.71 (4/5) | 1471 | 21 | 0.44 (4/5) | 619 | 23 | 0.22 (4/5) | 311 | 28 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 5 | **0.01 (4/5)** | **2** | 18 | 0.71 (4/5) | 1471 | 21 | 0.44 (4/5) | 619 | 23 | 0.22 (4/5) | 311 | 28 |

## bottom

| dataset | metric | b=2 | b=5 |
| --- | --- | --- | --- |
| CADETS_E3 | earliness D4 (n_miss) | 0.3852 (6) | 0.5869 (2) |
| CADETS_E3 | F D4 | 3.5000 | 7.0000 |
| CADETS_E3 | earliness D1 (n_miss) | 0.4203 (7) | 0.4828 (6) |
| CADETS_E3 | F D1 | 1.2500 | 5.0000 |
| CADETS_E3 | earliness D2 (n_miss) | 0.0000 (15) | 0.2909 (7) |
| CADETS_E3 | F D2 | 2.0000 | 6.7500 |
| CADETS_E3 | earliness D3 (n_miss) | 0.0000 (14) | 0.2909 (6) |
| CADETS_E3 | F D3 | 2.2500 | 6.7500 |
| THEIA_E3 | earliness D4 (n_miss) | 0.4252 (4) | 0.4252 (4) |
| THEIA_E3 | F D4 | 20.0000 | 20.0000 |
| THEIA_E3 | earliness D1 (n_miss) | 0.4246 (5) | 0.4246 (5) |
| THEIA_E3 | F D1 | 5.0000 | 10.6667 |
| THEIA_E3 | earliness D2 (n_miss) | 0.2154 (5) | 0.2154 (5) |
| THEIA_E3 | F D2 | 14.0000 | 14.0000 |
| THEIA_E3 | earliness D3 (n_miss) | 0.2705 (5) | 0.2705 (5) |
| THEIA_E3 | F D3 | 16.3333 | 16.3333 |

