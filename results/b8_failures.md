# B8 failures by class (tiling, repair budget 16, min width 0.50 m)

## By set

| set | n | repaired | repaired_strong_deformation | contradictory_constraints | grid_budget_exceeded | other | repaired [Wilson 95 %] |
|---|---|---|---|---|---|---|---|
| divers | 100 | 7 | 16 | 39 | 38 | 0 | 23.0 % [15.8 ; 32.2] |
| etoile | 320 | 16 | 49 | 143 | 112 | 0 | 20.3 % [16.3 ; 25.1] |
| plausible | 320 | 17 | 40 | 147 | 116 | 0 | 17.8 % [14.0 ; 22.4] |

## By graph

| graph | n | repaired | repaired_strong_deformation | contradictory_constraints | grid_budget_exceeded | other | repaired [Wilson 95 %] |
|---|---|---|---|---|---|---|---|
| anneau | 24 | 3 | 6 | 5 | 10 | 0 | 37.5 % [21.2 ; 57.3] |
| chaine | 24 | 1 | 1 | 10 | 12 | 0 | 8.3 % [2.3 ; 25.8] |
| etoile | 348 | 16 | 56 | 154 | 122 | 0 | 20.7 % [16.8 ; 25.3] |
| plausible | 344 | 20 | 42 | 160 | 122 | 0 | 18.0 % [14.3 ; 22.4] |

## By n_rooms

| n_rooms | n | repaired | repaired_strong_deformation | contradictory_constraints | grid_budget_exceeded | other | repaired [Wilson 95 %] |
|---|---|---|---|---|---|---|---|
| 3 | 12 | 1 | 3 | 5 | 3 | 0 | 33.3 % [13.8 ; 60.9] |
| 4 | 96 | 2 | 24 | 59 | 11 | 0 | 27.1 % [19.2 ; 36.7] |
| 5 | 180 | 15 | 35 | 91 | 39 | 0 | 27.8 % [21.8 ; 34.7] |
| 6 | 96 | 8 | 16 | 40 | 32 | 0 | 25.0 % [17.4 ; 34.5] |
| 7 | 252 | 11 | 21 | 100 | 120 | 0 | 12.7 % [9.1 ; 17.4] |
| 8 | 92 | 3 | 6 | 30 | 53 | 0 | 9.8 % [5.2 ; 17.6] |
| 9 | 8 | 0 | 0 | 2 | 6 | 0 | 0.0 % [0.0 ; 32.4] |
| 10 | 4 | 0 | 0 | 2 | 2 | 0 | 0.0 % [0.0 ; 49.0] |

Legalize alone (no tiling) repairs none: every generated plan leaves a gap, a
stationary point of the L1 optimum; the current code reports it as GapNeedsTiling
(the raw rows, older, label it invariant_viole). Visual examples per class:
`results/visuals/<set>/{repaired,proven-infeasible,unrecoverable-grid}/`.
