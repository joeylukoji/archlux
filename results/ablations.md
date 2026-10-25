# Ablations

90 source plans x 3 initialisations, seed 17, q_hat 660.118. Gains are paired against `repair`. Raw rows: `ablations_raw.csv`.

| config | n | valid | Wilson 95 % | cluster 95 % | median displ. (m) | surrogate gain | reference gain | predicted gain contradicted | valid and confirmed | FW at max_iter | spread across inits |
|---|--:|--:|:--:|:--:|--:|--:|--:|--:|--:|--:|--:|
| initial | 270 | 0 | [0.0 ; 1.4] | [0.0 ; 0.0] | nan | +nan % | +nan % | nan % | 0.0 % | 0 | nan |
| repair | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.250 | +0.0 % | +0.0 % | nan % | 0.0 % | 0 | 0.000 |
| fw_surrogate | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.827 | +1.6 % | +0.7 % | 7.9 % | 91.1 % | 0 | 0.000 |
| fw_surrogate_no_penalty | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.827 | +1.6 % | +0.7 % | 7.9 % | 91.1 % | 0 | 0.000 |
| fw_reference | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.827 | +1.6 % | +0.7 % | 0.0 % | 100.0 % | 0 | 0.000 |
| fw_surrogate_budget_0.5 | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.500 | +0.8 % | +0.4 % | 7.9 % | 91.1 % | 0 | 0.000 |
| fw_surrogate_budget_1 | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.827 | +1.5 % | +0.7 % | 7.9 % | 91.1 % | 0 | 0.000 |
| fw_surrogate_budget_2 | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.827 | +1.6 % | +0.7 % | 7.9 % | 91.1 % | 0 | 0.000 |
| fw_surrogate_budget_3 | 270 | 270 | [98.6 ; 100.0] | [100.0 ; 100.0] | 0.827 | +1.6 % | +0.7 % | 7.9 % | 91.1 % | 0 | 0.000 |
