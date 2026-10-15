# TABLE1_reset

## quiet-start

| dataset | attack | b | D1 ρ (k/5) | D1 d | D1 FP | D2 ρ (k/5) | D2 d | D2 FP | D3 ρ (k/5) | D3 d | D3 FP | FirstAlarm ρ (k/5) | FirstAlarm d | FirstAlarm FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CADETS_E3 | Nginx_Backdoor_06 | 2 | 0.24 (2/5) | 271 | 2 | 0.00† (1/5) | 7 | 5 | 0.79 (4/5) | 1226 | 5 | **0.43 (4/5)** | **529** | 5 |
| CADETS_E3 | Nginx_Backdoor_06 | 5 | 0.24 (2/5) | 271 | 6 | 0.21 (4/5) | 173 | 22 | **0.29 (5/5)** | **174** | 22 | **0.29 (5/5)** | **174** | 22 |
| CADETS_E3 | Nginx_Backdoor_12 | 2 | **0.28 (4/5)** | **254** | 2 | 0.07 (1/5) | 83 | 2 | 0.07 (1/5) | 83 | 3 | **0.28 (4/5)** | **254** | 4 |
| CADETS_E3 | Nginx_Backdoor_12 | 5 | 0.28 (4/5) | 254 | 5 | 0.10 (4/5) | 83 | 7 | 0.10 (4/5) | 83 | 8 | **0.12 (5/5)** | **83** | 9 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 2 | 0.31 (1/5) | 330 | 2 | 0.00† (1/5) | 32 | 7 | 0.00† (1/5) | 32 | 9 | **0.16† (2/5)** | **181** | 9 |
| THEIA_E3 | Firefox_Backdoor_Drakon_In_Memory | 5 | 0.31 (1/5) | 330 | 7 | 0.00† (1/5) | 32 | 7 | 0.00† (1/5) | 32 | 9 | **0.16† (2/5)** | **181** | 9 |

## spike-start

| dataset | attack | b | D1 ρ (k/5) | D1 d | D1 FP | D2 ρ (k/5) | D2 d | D2 FP | D3 ρ (k/5) | D3 d | D3 FP | FirstAlarm ρ (k/5) | FirstAlarm d | FirstAlarm FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CADETS_E3 | Nginx_Backdoor_13 | 2 | 0.05 (2/5) | 111 | 0 | miss (0/5) | miss | 3 | 0.94 (1/5) | 566 | 3 | **0.06 (3/5)** | **111** | 3 |
| CADETS_E3 | Nginx_Backdoor_13 | 5 | 0.06 (3/5) | 111 | 2 | 0.34 (3/5) | 251 | 11 | 0.34 (3/5) | 251 | 9 | **0.20 (4/5)** | **181** | 9 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 2 | **0.01 (4/5)** | **2** | 10 | 0.71 (4/5) | 1471 | 21 | 0.44 (4/5) | 619 | 23 | 0.22 (4/5) | 311 | 28 |
| THEIA_E3 | Browser_Extension_Drakon_Dropper | 5 | **0.01 (4/5)** | **2** | 18 | 0.71 (4/5) | 1471 | 21 | 0.44 (4/5) | 619 | 23 | 0.22 (4/5) | 311 | 28 |

## bottom

| dataset | metric | b=2 | b=5 |
| --- | --- | --- | --- |
| CADETS_E3 | earliness D4 (n_miss) | 0.4699 (4) | 0.7280 (1) |
| CADETS_E3 | F D4 | 4.2500 | 12.0000 |
| CADETS_E3 | earliness D1 (n_miss) | 0.4203 (7) | 0.4828 (6) |
| CADETS_E3 | F D1 | 1.2500 | 5.0000 |
| CADETS_E3 | earliness D2 (n_miss) | 0.1285 (13) | 0.5874 (4) |
| CADETS_E3 | F D2 | 3.0000 | 11.5000 |
| CADETS_E3 | earliness D3 (n_miss) | 0.1612 (9) | 0.5969 (3) |
| CADETS_E3 | F D3 | 3.2500 | 12.0000 |
| THEIA_E3 | earliness D4 (n_miss) | 0.4252 (4) | 0.4252 (4) |
| THEIA_E3 | F D4 | 20.0000 | 20.0000 |
| THEIA_E3 | earliness D1 (n_miss) | 0.4246 (5) | 0.4246 (5) |
| THEIA_E3 | F D1 | 5.0000 | 10.6667 |
| THEIA_E3 | earliness D2 (n_miss) | 0.2154 (5) | 0.2154 (5) |
| THEIA_E3 | F D2 | 14.0000 | 14.0000 |
| THEIA_E3 | earliness D3 (n_miss) | 0.2705 (5) | 0.2705 (5) |
| THEIA_E3 | F D3 | 16.3333 | 16.3333 |

