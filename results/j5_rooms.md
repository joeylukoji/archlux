# Coverage by room type, and with a varying sigma_hat

400 typed four-room source plans x 4 azimuths, 5 repetitions, alpha = 0.1, seed 17. Reference: frozen `SplitFluxOracle` (closed form, **not** a simulation). Synthetic plans only.

## 1. Per room (analytic surrogate rescaled per room, constant sigma_hat)

Raw rows: `j5_rooms_raw.csv`. Unit = one room; clusters = repetition x source.

| procedure | stratum | n | clusters | coverage | cluster 95 % CI | mean of reps [95 % CI over reps] | worst rep | mean width | below target |
|---|---|--:|--:|--:|:--:|:--:|--:|--:|:--:|
| passive | all | 8000 | 500 | 91.1 % | [90.4 ; 91.9] | 91.1 % [83.2 ; 99.1] | 82.8 % | 21.758 | no |
| passive | room_type=bathroom | 2000 | 500 | 91.6 % | [90.5 ; 92.8] | 91.6 % [84.4 ; 98.8] | 84.0 % | 21.758 | no |
| passive | room_type=bedroom | 2000 | 500 | 92.3 % | [91.2 ; 93.4] | 92.3 % [84.2 ; 100.4] | 83.2 % | 21.758 | no |
| passive | room_type=kitchen | 2000 | 500 | 90.2 % | [89.0 ; 91.5] | 90.3 % [82.1 ; 98.4] | 82.0 % | 21.758 | no |
| passive | room_type=living_room | 2000 | 500 | 90.4 % | [89.2 ; 91.6] | 90.4 % [82.0 ; 98.8] | 82.0 % | 21.758 | no |
| passive | sector=E | 2000 | 500 | 97.0 % | [96.2 ; 97.8] | 97.0 % [93.1 ; 101.0] | 92.0 % | 21.758 | no |
| passive | sector=N | 2000 | 500 | 99.5 % | [99.2 ; 99.8] | 99.5 % [98.4 ; 100.6] | 98.0 % | 21.758 | no |
| passive | sector=S | 2000 | 500 | 79.8 % | [78.1 ; 81.5] | 79.8 % [64.3 ; 95.3] | 64.5 % | 21.758 | no |
| passive | sector=W | 2000 | 500 | 88.2 % | [86.7 ; 89.6] | 88.2 % [76.6 ; 99.8] | 76.8 % | 21.758 | no |
| passive | level=high | 2571 | 500 | 78.7 % | [77.0 ; 80.6] | 80.0 % [64.3 ; 95.8] | 68.0 % | 20.922 | no |
| passive | level=low | 2801 | 500 | 99.3 % | [98.9 ; 99.5] | 99.2 % [98.0 ; 100.4] | 97.6 % | 22.094 | no |
| passive | level=mid | 2628 | 500 | 94.6 % | [93.8 ; 95.4] | 94.3 % [90.0 ; 98.7] | 91.1 % | 22.218 | no |
| passive_on_selected | all | 8000 | 500 | 59.2 % | [57.5 ; 61.0] | 59.2 % [35.4 ; 83.0] | 39.9 % | 21.758 | **yes** |
| passive_on_selected | room_type=bathroom | 2000 | 500 | 58.6 % | [56.1 ; 61.0] | 58.5 % [34.1 ; 83.0] | 41.0 % | 21.758 | **yes** |
| passive_on_selected | room_type=bedroom | 2000 | 500 | 59.7 % | [57.4 ; 62.0] | 59.7 % [35.3 ; 84.1] | 40.5 % | 21.758 | **yes** |
| passive_on_selected | room_type=kitchen | 2000 | 500 | 59.7 % | [57.3 ; 62.0] | 59.7 % [37.4 ; 82.0] | 39.8 % | 21.758 | **yes** |
| passive_on_selected | room_type=living_room | 2000 | 500 | 59.0 % | [56.6 ; 61.2] | 58.9 % [34.5 ; 83.4] | 38.5 % | 21.758 | **yes** |
| passive_on_selected | sector=E | 2000 | 500 | 67.4 % | [64.5 ; 70.2] | 67.4 % [46.0 ; 88.8] | 51.5 % | 21.758 | **yes** |
| passive_on_selected | sector=N | 2000 | 500 | 64.6 % | [61.9 ; 67.3] | 64.7 % [38.7 ; 90.6] | 41.2 % | 21.758 | no |
| passive_on_selected | sector=S | 2000 | 500 | 56.9 % | [54.0 ; 60.0] | 56.9 % [40.3 ; 73.5] | 44.0 % | 21.758 | **yes** |
| passive_on_selected | sector=W | 2000 | 500 | 47.9 % | [45.2 ; 50.5] | 47.9 % [15.5 ; 80.4] | 23.0 % | 21.758 | **yes** |
| passive_on_selected | level=high | 2924 | 500 | 50.1 % | [48.0 ; 52.2] | 51.1 % [36.2 ; 65.9] | 42.5 % | 20.868 | **yes** |
| passive_on_selected | level=low | 2614 | 500 | 57.8 % | [55.0 ; 60.8] | 55.2 % [15.8 ; 94.7] | 21.0 % | 22.157 | no |
| passive_on_selected | level=mid | 2462 | 500 | 71.5 % | [69.5 ; 73.4] | 70.4 % [51.8 ; 89.1] | 57.0 % | 22.393 | **yes** |
| policy | all | 8000 | 500 | 90.1 % | [89.4 ; 90.7] | 90.1 % [84.9 ; 95.2] | 83.2 % | 32.930 | no |
| policy | room_type=bathroom | 2000 | 500 | 89.8 % | [88.6 ; 91.1] | 89.8 % [84.9 ; 94.8] | 83.5 % | 32.930 | no |
| policy | room_type=bedroom | 2000 | 500 | 90.5 % | [89.0 ; 91.6] | 90.5 % [85.8 ; 95.1] | 85.0 % | 32.930 | no |
| policy | room_type=kitchen | 2000 | 500 | 89.5 % | [88.2 ; 90.8] | 89.5 % [82.9 ; 96.1] | 80.2 % | 32.930 | no |
| policy | room_type=living_room | 2000 | 500 | 90.5 % | [89.2 ; 91.6] | 90.5 % [85.8 ; 95.1] | 84.2 % | 32.930 | no |
| policy | sector=E | 2000 | 500 | 94.8 % | [93.9 ; 95.7] | 94.8 % [90.9 ; 98.8] | 89.2 % | 32.930 | no |
| policy | sector=N | 2000 | 500 | 94.6 % | [93.7 ; 95.5] | 94.6 % [90.8 ; 98.4] | 92.5 % | 32.930 | no |
| policy | sector=S | 2000 | 500 | 80.8 % | [78.9 ; 82.6] | 80.7 % [75.0 ; 86.5] | 74.2 % | 32.930 | **yes** |
| policy | sector=W | 2000 | 500 | 90.0 % | [88.8 ; 91.2] | 90.0 % [80.8 ; 99.3] | 77.0 % | 32.930 | no |
| policy | level=high | 2924 | 500 | 77.5 % | [75.8 ; 79.1] | 76.2 % [64.3 ; 88.1] | 61.6 % | 33.115 | **yes** |
| policy | level=low | 2614 | 500 | 99.8 % | [99.6 ; 99.9] | 99.8 % [99.2 ; 100.4] | 98.9 % | 32.705 | no |
| policy | level=mid | 2462 | 500 | 94.6 % | [93.8 ; 95.5] | 95.0 % [88.5 ; 101.4] | 87.1 % | 32.950 | no |

Guarantee of each procedure:

- `passive`: guaranteed: marginal, exchangeable sources
- `passive_on_selected`: not guaranteed: the optimizer selected these plans through the surrogate
- `policy`: guaranteed: marginal, exchangeable sources, policy frozen before calibration

## 2. Per plan, bootstrap ensemble of 5 DenseSurrogate (varying sigma_hat)

Members trained on 200 other source plans (`pool-*`, one azimuth each), never in any split. Raw rows: `j5_ensemble_raw.csv`.

| procedure | stratum | n | clusters | coverage | cluster 95 % CI | mean of reps [95 % CI over reps] | worst rep | mean width | below target |
|---|---|--:|--:|--:|:--:|:--:|--:|--:|:--:|
| passive | all | 2000 | 500 | 88.3 % | [86.8 ; 90.0] | 88.3 % [85.5 ; 91.2] | 85.8 % | 5.869 | no |
| passive | sector=E | 500 | 500 | 94.2 % | [92.2 ; 96.2] | 94.2 % [93.2 ; 95.2] | 93.0 % | 6.004 | no |
| passive | sector=N | 500 | 500 | 86.8 % | [83.6 ; 89.8] | 86.8 % [82.0 ; 91.6] | 83.0 % | 4.751 | no |
| passive | sector=S | 500 | 500 | 85.2 % | [82.2 ; 88.4] | 85.2 % [76.7 ; 93.7] | 77.0 % | 5.971 | no |
| passive | sector=W | 500 | 500 | 87.2 % | [84.2 ; 90.0] | 87.2 % [84.8 ; 89.6] | 85.0 % | 6.752 | **yes** |
| passive | level=high | 664 | 500 | 82.7 % | [79.8 ; 85.6] | 82.6 % [76.6 ; 88.6] | 76.9 % | 5.912 | **yes** |
| passive | level=low | 663 | 497 | 92.2 % | [90.0 ; 94.2] | 92.5 % [89.4 ; 95.7] | 89.8 % | 4.978 | no |
| passive | level=mid | 673 | 454 | 90.2 % | [87.7 ; 92.4] | 90.4 % [87.2 ; 93.6] | 86.7 % | 6.706 | no |
| passive | sigma_level=high | 755 | 404 | 88.2 % | [85.8 ; 90.5] | 88.0 % [83.1 ; 92.8] | 83.0 % | 9.353 | no |
| passive | sigma_level=low | 611 | 361 | 87.4 % | [84.6 ; 90.1] | 86.9 % [79.9 ; 94.0] | 79.2 % | 2.549 | no |
| passive | sigma_level=mid | 634 | 382 | 89.4 % | [86.9 ; 92.0] | 89.5 % [85.9 ; 93.1] | 85.8 % | 4.920 | no |
| passive_on_selected | all | 2000 | 500 | 45.1 % | [43.0 ; 47.2] | 45.1 % [35.3 ; 54.9] | 37.0 % | 9.590 | **yes** |
| passive_on_selected | sector=E | 500 | 500 | 57.2 % | [53.0 ; 61.8] | 57.2 % [51.0 ; 63.4] | 52.0 % | 9.908 | **yes** |
| passive_on_selected | sector=N | 500 | 500 | 44.2 % | [39.8 ; 48.6] | 44.2 % [32.8 ; 55.6] | 34.0 % | 10.645 | **yes** |
| passive_on_selected | sector=S | 500 | 500 | 54.0 % | [49.8 ; 58.2] | 54.0 % [35.5 ; 72.5] | 34.0 % | 7.983 | **yes** |
| passive_on_selected | sector=W | 500 | 500 | 25.0 % | [21.4 ; 28.8] | 25.0 % [17.6 ; 32.4] | 19.0 % | 9.824 | **yes** |
| passive_on_selected | level=high | 859 | 500 | 44.0 % | [41.0 ; 47.2] | 45.0 % [27.8 ; 62.3] | 30.1 % | 7.933 | **yes** |
| passive_on_selected | level=low | 432 | 354 | 44.4 % | [40.4 ; 48.3] | 43.3 % [36.9 ; 49.7] | 36.2 % | 10.476 | **yes** |
| passive_on_selected | level=mid | 709 | 421 | 46.8 % | [43.5 ; 50.2] | 44.6 % [32.5 ; 56.6] | 31.7 % | 11.059 | **yes** |
| passive_on_selected | sigma_level=high | 1127 | 493 | 40.9 % | [38.0 ; 43.7] | 41.2 % [31.1 ; 51.3] | 34.0 % | 14.118 | **yes** |
| passive_on_selected | sigma_level=low | 419 | 332 | 53.0 % | [48.3 ; 57.6] | 51.7 % [36.8 ; 66.7] | 32.9 % | 2.494 | **yes** |
| passive_on_selected | sigma_level=mid | 454 | 329 | 48.2 % | [43.7 ; 52.6] | 48.4 % [40.1 ; 56.7] | 40.8 % | 4.899 | **yes** |
| policy | all | 2000 | 500 | 90.3 % | [88.9 ; 91.6] | 90.3 % [87.5 ; 93.1] | 88.2 % | 30.322 | no |
| policy | sector=E | 500 | 500 | 90.4 % | [87.6 ; 92.8] | 90.4 % [88.0 ; 92.8] | 89.0 % | 31.226 | no |
| policy | sector=N | 500 | 500 | 91.4 % | [88.6 ; 93.8] | 91.4 % [86.5 ; 96.3] | 86.0 % | 33.786 | no |
| policy | sector=S | 500 | 500 | 98.0 % | [96.6 ; 99.0] | 98.0 % [95.8 ; 100.2] | 95.0 % | 25.155 | no |
| policy | sector=W | 500 | 500 | 81.4 % | [78.0 ; 84.6] | 81.4 % [74.1 ; 88.7] | 75.0 % | 31.123 | **yes** |
| policy | level=high | 859 | 500 | 92.4 % | [90.7 ; 94.1] | 92.3 % [90.1 ; 94.5] | 90.8 % | 25.403 | no |
| policy | level=low | 432 | 354 | 93.3 % | [90.9 ; 95.5] | 93.5 % [89.9 ; 97.1] | 89.4 % | 33.593 | no |
| policy | level=mid | 709 | 421 | 85.9 % | [83.5 ; 88.2] | 85.8 % [82.0 ; 89.6] | 82.9 % | 34.290 | **yes** |
| policy | sigma_level=high | 1127 | 493 | 95.3 % | [94.1 ; 96.5] | 95.4 % [92.9 ; 97.9] | 92.6 % | 44.633 | no |
| policy | sigma_level=low | 419 | 332 | 85.9 % | [82.0 ; 89.3] | 86.3 % [81.0 ; 91.7] | 80.4 % | 7.809 | no |
| policy | sigma_level=mid | 454 | 329 | 81.9 % | [78.0 ; 85.6] | 81.9 % [76.2 ; 87.6] | 77.5 % | 15.575 | **yes** |

Guarantee of each procedure:

- `passive`: guaranteed: marginal, exchangeable sources
- `passive_on_selected`: not guaranteed: the optimizer selected these plans through the surrogate
- `policy`: guaranteed: marginal, exchangeable sources, policy frozen before calibration
