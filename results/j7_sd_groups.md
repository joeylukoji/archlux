# B7 breakdown against the closed form (not against simulations)

400 typed four-room synthetic source plans x 4 azimuths, split by source (train 200 / test 200 sources), seed 17. Reference: frozen `SplitFluxOracle`, a closed form: these errors say how well a surrogate reproduces that oracle, **not** daylight. Intervals resample whole source plans. Glazing is not represented (no openings, oracle ignores glazing): that breakdown needs the Swiss Dwellings run of `j7_sd_labels.py`.

## Plan level: `analytic_affine`

| grouping | group | n | clusters | MAE (score) [95 % cluster CI] | bias (score) [95 % CI] | relative MAE | Spearman |
|---|---|--:|--:|:--:|:--:|--:|--:|
| all | all | 800 | 200 | 11.400 [11.029 ; 11.770] | -0.118 [-0.278 ; +0.050] | 6.6 % | +0.983 |
| orientation | 0 | 200 | 200 | 4.821 [4.530 ; 5.134] | +3.104 [+2.501 ; +3.713] | 4.4 % | +0.859 |
| orientation | 180 | 200 | 200 | 16.951 [15.786 ; 18.136] | -14.687 [-16.340 ; -13.088] | 6.4 % | +0.945 |
| orientation | 270 | 200 | 200 | 16.971 [16.227 ; 17.681] | +16.971 [+16.257 ; +17.744] | 8.7 % | +0.998 |
| orientation | 90 | 200 | 200 | 6.856 [6.035 ; 7.724] | -5.858 [-6.857 ; -4.850] | 5.5 % | +0.996 |
| dominant_room_type | bathroom | 200 | 50 | 11.258 [10.550 ; 12.002] | -0.141 [-0.413 ; +0.137] | 6.5 % | +0.981 |
| dominant_room_type | bedroom | 212 | 53 | 10.935 [10.321 ; 11.587] | -0.102 [-0.416 ; +0.207] | 6.3 % | +0.984 |
| dominant_room_type | kitchen | 204 | 51 | 11.747 [11.079 ; 12.448] | -0.348 [-0.718 ; +0.044] | 6.9 % | +0.981 |
| dominant_room_type | living_room | 184 | 46 | 11.705 [10.939 ; 12.538] | +0.145 [-0.188 ; +0.494] | 6.7 % | +0.980 |
| glazing | not represented (no openings; oracle ignores glazing) | 800 | 200 | 11.400 [11.050 ; 11.757] | -0.118 [-0.274 ; +0.043] | 6.6 % | +0.983 |

## Plan level: `dense`

| grouping | group | n | clusters | MAE (score) [95 % cluster CI] | bias (score) [95 % CI] | relative MAE | Spearman |
|---|---|--:|--:|:--:|:--:|--:|--:|
| all | all | 800 | 200 | 0.838 [0.714 ; 0.992] | +0.020 [-0.051 ; +0.097] | 0.5 % | +0.999 |
| orientation | 0 | 200 | 200 | 0.747 [0.643 ; 0.859] | +0.021 [-0.131 ; +0.171] | 0.7 % | +0.994 |
| orientation | 180 | 200 | 200 | 1.016 [0.881 ; 1.163] | -0.073 [-0.279 ; +0.125] | 0.4 % | +0.997 |
| orientation | 270 | 200 | 200 | 0.737 [0.618 ; 0.872] | -0.129 [-0.304 ; +0.028] | 0.4 % | +0.999 |
| orientation | 90 | 200 | 200 | 0.852 [0.616 ; 1.144] | +0.259 [-0.010 ; +0.554] | 0.7 % | +0.997 |
| dominant_room_type | bathroom | 200 | 50 | 0.727 [0.543 ; 1.002] | -0.030 [-0.162 ; +0.108] | 0.4 % | +0.999 |
| dominant_room_type | bedroom | 212 | 53 | 0.987 [0.731 ; 1.321] | -0.078 [-0.213 ; +0.046] | 0.6 % | +0.999 |
| dominant_room_type | kitchen | 204 | 51 | 0.690 [0.572 ; 0.840] | +0.116 [-0.037 ; +0.302] | 0.4 % | +1.000 |
| dominant_room_type | living_room | 184 | 46 | 0.952 [0.641 ; 1.338] | +0.080 [-0.057 ; +0.223] | 0.5 % | +0.998 |
| glazing | not represented (no openings; oracle ignores glazing) | 800 | 200 | 0.838 [0.713 ; 0.974] | +0.020 [-0.048 ; +0.097] | 0.5 % | +0.999 |

## Plan level: `ensemble`

| grouping | group | n | clusters | MAE (score) [95 % cluster CI] | bias (score) [95 % CI] | relative MAE | Spearman |
|---|---|--:|--:|:--:|:--:|--:|--:|
| all | all | 800 | 200 | 0.783 [0.668 ; 0.924] | +0.136 [+0.092 ; +0.179] | 0.5 % | +0.999 |
| orientation | 0 | 200 | 200 | 0.736 [0.622 ; 0.863] | +0.148 [-0.013 ; +0.317] | 0.7 % | +0.992 |
| orientation | 180 | 200 | 200 | 0.807 [0.690 ; 0.938] | +0.226 [+0.055 ; +0.388] | 0.3 % | +0.998 |
| orientation | 270 | 200 | 200 | 0.767 [0.647 ; 0.908] | +0.037 [-0.143 ; +0.199] | 0.4 % | +0.999 |
| orientation | 90 | 200 | 200 | 0.823 [0.648 ; 1.023] | +0.135 [-0.090 ; +0.347] | 0.7 % | +0.996 |
| dominant_room_type | bathroom | 200 | 50 | 0.631 [0.477 ; 0.844] | +0.167 [+0.095 ; +0.252] | 0.4 % | +0.999 |
| dominant_room_type | bedroom | 212 | 53 | 0.896 [0.606 ; 1.247] | +0.095 [+0.016 ; +0.171] | 0.5 % | +0.999 |
| dominant_room_type | kitchen | 204 | 51 | 0.663 [0.539 ; 0.834] | +0.122 [+0.015 ; +0.208] | 0.4 % | +1.000 |
| dominant_room_type | living_room | 184 | 46 | 0.952 [0.690 ; 1.262] | +0.167 [+0.066 ; +0.264] | 0.5 % | +0.999 |
| glazing | not represented (no openings; oracle ignores glazing) | 800 | 200 | 0.783 [0.668 ; 0.912] | +0.136 [+0.091 ; +0.184] | 0.5 % | +0.999 |

## Room level: analytic surrogate rescaled per room

| grouping | group | n | clusters | MAE (score) [95 % cluster CI] | bias (score) [95 % CI] | relative MAE | Spearman |
|---|---|--:|--:|:--:|:--:|--:|--:|
| all | all | 3200 | 200 | 4.387 [4.276 ; 4.495] | -0.020 [-0.049 ; +0.009] | 10.2 % | +0.963 |
| room_type | bathroom | 800 | 200 | 4.235 [4.036 ; 4.425] | -0.026 [-0.444 ; +0.375] | 9.7 % | +0.964 |
| room_type | bedroom | 800 | 200 | 4.325 [4.130 ; 4.526] | -0.093 [-0.545 ; +0.345] | 10.1 % | +0.960 |
| room_type | kitchen | 800 | 200 | 4.633 [4.422 ; 4.851] | -0.064 [-0.536 ; +0.403] | 10.7 % | +0.962 |
| room_type | living_room | 800 | 200 | 4.355 [4.141 ; 4.555] | +0.102 [-0.355 ; +0.524] | 10.2 % | +0.965 |
| orientation | 0 | 800 | 200 | 2.948 [2.814 ; 3.086] | +1.796 [+1.658 ; +1.928] | 10.9 % | +0.894 |
| orientation | 180 | 800 | 200 | 6.224 [5.964 ; 6.480] | -4.923 [-5.295 ; -4.542] | 9.5 % | +0.955 |
| orientation | 270 | 800 | 200 | 5.025 [4.805 ; 5.248] | +3.599 [+3.393 ; +3.806] | 10.3 % | +0.969 |
| orientation | 90 | 800 | 200 | 3.351 [3.168 ; 3.536] | -0.552 [-0.872 ; -0.242] | 10.8 % | +0.919 |
