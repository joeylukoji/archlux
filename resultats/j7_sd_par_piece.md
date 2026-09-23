# Jalon 7 — prediction par piece contre simulations reelles

Cible `sun_201803211200_mean` (Swiss Dwellings v3.0.0). Corpus MSD joint aux
simulations, granularite **piece**.

## A. Correlations sur l'ensemble apparie (4 239 pieces)

| predicteur | Pearson | Spearman |
|---|--:|--:|
| **aire au sol seule** | **+0,387** | **+0,590** |
| analytique par piece (extensive) | +0,151 | +0,403 |
| analytique / aire (intensive) | +0,076 | **+0,085** |
| 1 / aire | -0,318 | -0,590 |

## B. Generalisation, decoupage **par site** (test 2 346 pieces)

| modele | MAE | MAE relative | R2 | Spearman |
|---|--:|--:|--:|--:|
| constante (moyenne du train) | 0,448 | 91,5 % | -0,000 | — |
| **aire au sol seule** | **0,403** | 82,3 % | **+0,150** | **+0,572** |
| analytique par piece | 0,448 | 91,5 % | -0,000 | **-0,342** |

Conforme a alpha = 0,10 sur l'analytique : couverture **88,5 %** pour 90 % vises,
largeur 1,554, n_calibration 2 708.

## Lecture

**Le substitut analytique ne predit que la taille des pieces.** Normalise par l'aire,
son rang tombe a `rho = +0,085` : il ne reste presque rien. Tout son pouvoir predictif
vient de ce qu'il croit avec la surface, pas de sa physique — ni la regle de profondeur
CIBSE, ni la table a huit secteurs n'apportent de signal.

**L'aire au sol seule le bat.** `rho = +0,590` contre `+0,403`, et `R2 = +0,150` contre
`-0,000` en generalisation. Une variable triviale, disponible sans aucun modele, predit
mieux que le substitut du depot.

**Le peu de signal ne survit pas au changement de site.** Sur l'ensemble apparie
l'analytique correle positivement (`rho = +0,403`) ; sur des sites **disjoints** de
l'entrainement, le rang s'inverse (`rho = -0,342`). C'est exactement ce que le
decoupage par site sert a reveler, et ce qu'un decoupage par appartement aurait cache.

**La couverture conforme flechit legerement** — 88,5 % pour 90 % vises. Le theoreme
suppose l'echangeabilite ; des sites disjoints ne le sont pas. L'ecart est faible et va
dans le sens attendu : c'est une illustration mesuree de la limite documentee dans
`limites.md`, pas un defaut d'implementation.

## Portee

Une colonne sur 126, 2 000 appartements parcourus, une irradiance a instant fixe qui
n'est pas un sDA. Ces chiffres disent ce que vaut **ce** substitut sur **cette** cible,
pas ce que vaudrait un modele entraine sur les baies et l'environnement.
