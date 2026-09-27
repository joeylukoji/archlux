# Jalon 7 — substitut contre simulations Swiss Dwellings

cible : `sun_201803211200_mean`, moyenne ponderee par surface
decoupage **par site** (graine 17) : train 1205 / calibration 426 / test 369
sites : 133 / 44 / 45

cible sur le test : moyenne 0.677, ecart-type 0.390

| modele | MAE | MAE relative | R2 |
|---|--:|--:|--:|
| constante (moyenne du train) | 0.267 | 39.5 % | 0.000 |
| analytique recale (-0.0000f+0.64) | 0.268 | 39.6 % | -0.000 |
| perceptron (sans baies) | 0.353 | 52.2 % | -0.557 |
| perceptron **avec baies** | 0.307 | 45.4 % | -0.220 |

conforme alpha=0,10 : couverture mesuree **90.2 %** (visee 90 %), largeur moyenne 1.534, n_calibration 426
