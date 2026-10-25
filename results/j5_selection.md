# Coverage before and after selection

400 source plans x 4 azimuths, 10 repetitions, alpha = 0.1, seed 17. Raw rows: `j5_selection_raw.csv`.

| procedure | stratum | n | clusters | coverage | cluster 95 % CI | mean of reps [95 % CI over reps] | worst rep | mean width | below target |
|---|---|--:|--:|--:|:--:|:--:|--:|--:|:--:|
| passive | all | 4000 | 1000 | 88.6 % | [87.6 ; 89.5] | 88.6 % [85.9 ; 91.4] | 82.8 % | 31.271 | no |
| passive | sector=E | 1000 | 1000 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.271 | no |
| passive | sector=N | 1000 | 1000 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.271 | no |
| passive | sector=S | 1000 | 1000 | 61.7 % | [58.6 ; 64.7] | 61.7 % [56.1 ; 67.3] | 52.0 % | 31.271 | **yes** |
| passive | sector=W | 1000 | 1000 | 92.8 % | [91.1 ; 94.4] | 92.8 % [86.8 ; 98.8] | 78.0 % | 31.271 | no |
| passive | level=high | 1532 | 998 | 74.2 % | [72.1 ; 76.3] | 74.3 % [67.3 ; 81.3] | 59.6 % | 31.228 | **yes** |
| passive | level=low | 1291 | 962 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.362 | no |
| passive | level=mid | 1177 | 740 | 95.0 % | [93.7 ; 96.2] | 94.7 % [90.3 ; 99.1] | 82.2 % | 31.227 | no |
| passive | sigma_level=constant | 4000 | 1000 | 88.6 % | [87.6 ; 89.5] | 88.6 % [85.9 ; 91.4] | 82.8 % | 31.271 | no |
| passive_on_selected | all | 4000 | 1000 | 75.9 % | [74.6 ; 77.2] | 76.0 % [71.9 ; 80.0] | 70.2 % | 31.271 | **yes** |
| passive_on_selected | sector=E | 1000 | 1000 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.271 | no |
| passive_on_selected | sector=N | 1000 | 1000 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.271 | no |
| passive_on_selected | sector=S | 1000 | 1000 | 64.1 % | [61.1 ; 67.0] | 64.1 % [56.9 ; 71.3] | 53.0 % | 31.271 | **yes** |
| passive_on_selected | sector=W | 1000 | 1000 | 39.7 % | [36.7 ; 42.8] | 39.7 % [30.2 ; 49.2] | 28.0 % | 31.271 | **yes** |
| passive_on_selected | level=high | 1900 | 1000 | 49.4 % | [46.8 ; 52.0] | 49.2 % [40.6 ; 57.9] | 33.3 % | 31.264 | **yes** |
| passive_on_selected | level=low | 994 | 739 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.564 | no |
| passive_on_selected | level=mid | 1106 | 723 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 31.019 | no |
| passive_on_selected | sigma_level=constant | 4000 | 1000 | 75.9 % | [74.6 ; 77.2] | 76.0 % [71.9 ; 80.0] | 70.2 % | 31.271 | **yes** |
| policy | all | 4000 | 1000 | 91.3 % | [90.4 ; 92.2] | 91.3 % [88.2 ; 94.4] | 83.5 % | 38.005 | no |
| policy | sector=E | 1000 | 1000 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 38.005 | no |
| policy | sector=N | 1000 | 1000 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 38.005 | no |
| policy | sector=S | 1000 | 1000 | 83.1 % | [80.6 ; 85.3] | 83.1 % [79.9 ; 86.3] | 73.0 % | 38.005 | **yes** |
| policy | sector=W | 1000 | 1000 | 82.2 % | [79.9 ; 84.4] | 82.2 % [72.5 ; 91.9] | 61.0 % | 38.005 | no |
| policy | level=high | 1900 | 1000 | 81.7 % | [79.7 ; 83.7] | 81.9 % [76.0 ; 87.8] | 70.1 % | 37.960 | **yes** |
| policy | level=low | 994 | 739 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 38.237 | no |
| policy | level=mid | 1106 | 723 | 100.0 % | [100.0 ; 100.0] | 100.0 % [100.0 ; 100.0] | 100.0 % | 37.876 | no |
| policy | sigma_level=constant | 4000 | 1000 | 91.3 % | [90.4 ; 92.2] | 91.3 % [88.2 ; 94.4] | 83.5 % | 38.005 | no |

Guarantee of each procedure:

- `passive`: guaranteed: marginal, exchangeable sources
- `passive_on_selected`: not guaranteed: the optimizer selected these plans through the surrogate
- `policy`: guaranteed: marginal, exchangeable sources, policy frozen before calibration
