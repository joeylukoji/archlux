# Jalon 8 — légaliser des plans **réellement générés**

HouseDiffusion (CVPR 2023), poids officiels `model250000.pt`, RPLAN, **1000 pas** sans rééchantillonnage. 320 plans, 1960 pièces. Échelle 10.528 m/unité, calée sur l'aire médiane MSD (79,0 m²).

**0 plan(s) sur 320 sont valides avant correction.**

## État des sorties du générateur

| | médiane | moyenne | p95 |
|---|--:|--:|--:|
| pièces recouvertes par pièce | 1.60 | 1.58 | 3.15 |
| part de jour dans l'enveloppe | 24.7% | 25.1% | 46.6% |
| dont trous **intérieurs** | 0.0% | 0.0% | 0.0% |
| morceaux disjoints de l'union | 2 | 2.38 | 4 |
| cellules de la trame implicite | 64 | 70 | 130 |

## Réparation

Référentiel `largeur_min = 0.50 m`.

| mode | budget | n | réparés | IC 95 % | t médian | déplacement médian |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` seul | — | 320 | **0.0 %** | [0.0, 1.2] | 2.9 ms | — |
| `pavage=True` | 0 | 320 | **0.6 %** | [0.2, 2.2] | 0.8 ms | 1.52 m (18% du côté) |
| `pavage=True` | 4 | 320 | **10.6 %** | [7.7, 14.5] | 1.4 ms | 3.82 m (41% du côté) |
| `pavage=True` | 8 | 320 | **16.6 %** | [12.9, 21.0] | 2.9 ms | 3.95 m (38% du côté) |
| `pavage=True` | 16 | 320 | **17.8 %** | [14.0, 22.4] | 3.3 ms | 3.95 m (38% du côté) |

## Ce que coûte — et rapporte — un plancher sur la largeur

| `largeur_min` | n | valides | **dont aucune pièce écrasée** | plus petit côté | déplacement médian |
|--:|--:|--:|--:|--:|--:|
| 0.00 m | 320 | 59.7 % [54.2, 64.9] | **13.8 %** [10.4, 18.0] | 0.000 m | 48% |
| 0.25 m | 320 | 17.8 % [14.0, 22.4] | **13.8 %** [10.4, 18.0] | 0.740 m | 38% |
| 0.50 m *(nominal)* | 320 | 17.8 % [14.0, 22.4] | **17.8 %** [14.0, 22.4] | 0.740 m | 38% |
| 1.00 m | 320 | 17.8 % [14.0, 22.4] | **17.8 %** [14.0, 22.4] | 1.000 m | 38% |
| 1.80 m | 320 | 17.8 % [14.0, 22.4] | **17.8 %** [14.0, 22.4] | 1.800 m | 38% |

## Réparation par taille de programme

| pièces | n | réparés (budget 16) | cellules médianes |
|--:|--:|--:|--:|
| 4 | 40 | 25.0 % | 30 |
| 5 | 80 | 28.8 % | 49 |
| 6 | 40 | 20.0 % | 63 |
| 7 | 120 | 11.7 % | 81 |
| 8 | 40 | 5.0 % | 109 |

## Réparation par topologie du graphe d'accès

| topologie | n | réparés (budget 16) | jour méd. | recouvr. méd. | morceaux méd. |
|---|--:|--:|--:|--:|--:|
| `plausible` | 320 | 17.8 % | 24.7% | 1.60 | 2 |

## Échecs

{'base:invariant_viole': 320, 'pavage0:trame': 318, 'pavage4:infaisable': 57, 'pavage8:infaisable': 121, 'pavage16:infaisable': 601, 'pavage4:trame': 229, 'pavage8:trame': 146, 'pavage16:trame': 580}

## Rejets à la construction

aucun
