# Milestone 7: surrogate against Swiss Dwellings simulations

target: `sun_201803211200_mean`, area-weighted mean
split **by site** (seed 17): train 1205 / calibration 426 / test 369
sites: 133 / 44 / 45

target on the test set: mean 0.677, standard deviation 0.390

| model | MAE | relative MAE | R2 |
|---|--:|--:|--:|
| constant (train mean) | 0.267 | 39.5 % | 0.000 |
| rescaled analytic (-0.0000f+0.64) | 0.268 | 39.6 % | -0.000 |
| perceptron (no glazing) | 0.353 | 52.2 % | -0.557 |
| perceptron **with glazing** | 0.307 | 45.4 % | -0.220 |

conformal alpha=0.10: measured coverage **90.2 %** (target 90 %), mean width 1.534, n_calibration 426
