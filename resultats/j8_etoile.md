# Jalon 8 — légaliser des plans **réellement générés**

HouseDiffusion (CVPR 2023), poids officiels `model250000.pt`, RPLAN, **1000 pas** sans rééchantillonnage. 320 plans, 1960 pièces. Échelle 11.605 m/unité, calée sur l'aire médiane MSD (79,0 m²).

**0 plan(s) sur 320 sont valides avant correction.**

## État des sorties du générateur

| | médiane | moyenne | p95 |
|---|--:|--:|--:|
| pièces recouvertes par pièce | 0.80 | 0.81 | 1.61 |
| part de jour dans l'enveloppe | 28.6% | 29.9% | 48.7% |
| dont trous **intérieurs** | 0.0% | 0.0% | 0.0% |
| morceaux disjoints de l'union | 4 | 3.75 | 6 |
| cellules de la trame implicite | 80 | 81 | 132 |

## Réparation

Référentiel `largeur_min = 0.50 m`.

| mode | budget | n | réparés | IC 95 % | t médian | déplacement médian |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` seul | — | 320 | **0.0 %** | [0.0, 1.2] | 3.0 ms | — |
| `pavage=True` | 0 | 320 | **0.6 %** | [0.2, 2.2] | 0.9 ms | 1.68 m (18% du côté) |
| `pavage=True` | 4 | 320 | **10.9 %** | [8.0, 14.8] | 1.4 ms | 3.72 m (36% du côté) |
| `pavage=True` | 8 | 320 | **18.4 %** | [14.6, 23.1] | 3.0 ms | 4.08 m (40% du côté) |
| `pavage=True` | 16 | 320 | **20.3 %** | [16.3, 25.1] | 3.6 ms | 4.35 m (43% du côté) |

## Ce que coûte — et rapporte — un plancher sur la largeur

| `largeur_min` | n | valides | **dont aucune pièce écrasée** | plus petit côté | déplacement médian |
|--:|--:|--:|--:|--:|--:|
| 0.00 m | 320 | 60.9 % [55.5, 66.1] | **19.1 %** [15.1, 23.7] | 0.000 m | 56% |
| 0.25 m | 320 | 20.3 % [16.3, 25.1] | **19.1 %** [15.1, 23.7] | 1.360 m | 43% |
| 0.50 m *(nominal)* | 320 | 20.3 % [16.3, 25.1] | **20.3 %** [16.3, 25.1] | 1.360 m | 43% |
| 1.00 m | 320 | 20.3 % [16.3, 25.1] | **20.3 %** [16.3, 25.1] | 1.360 m | 43% |
| 1.80 m | 320 | 20.3 % [16.3, 25.1] | **20.3 %** [16.3, 25.1] | 1.800 m | 43% |

## Réparation par taille de programme

| pièces | n | réparés (budget 16) | cellules médianes |
|--:|--:|--:|--:|
| 4 | 40 | 25.0 % | 32 |
| 5 | 80 | 25.0 % | 56 |
| 6 | 40 | 30.0 % | 78 |
| 7 | 120 | 13.3 % | 99 |
| 8 | 40 | 17.5 % | 126 |

## Réparation par topologie du graphe d'accès

| topologie | n | réparés (budget 16) | jour méd. | recouvr. méd. | morceaux méd. |
|---|--:|--:|--:|--:|--:|
| `etoile` | 320 | 20.3 % | 28.6% | 0.80 | 4 |

## Échecs

{'base:invariant_viole': 320, 'pavage0:trame': 318, 'pavage4:infaisable': 50, 'pavage8:infaisable': 114, 'pavage16:infaisable': 585, 'pavage4:trame': 235, 'pavage8:trame': 147, 'pavage16:trame': 560}

## Rejets à la construction

aucun
