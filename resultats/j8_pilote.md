# Jalon 8 — légaliser des plans **réellement générés**

HouseDiffusion (CVPR 2023), poids officiels `model250000.pt`, RPLAN, **1000 pas** sans rééchantillonnage. 48 plans, 294 pièces. Échelle 11.661 m/unité, calée sur l'aire médiane MSD (79,0 m²).

**0 plan(s) sur 48 sont valides avant correction.**

## État des sorties du générateur

| | médiane | moyenne | p95 |
|---|--:|--:|--:|
| pièces recouvertes par pièce | 0.80 | 0.84 | 1.64 |
| part de jour dans l'enveloppe | 26.6% | 28.3% | 44.9% |
| dont trous **intérieurs** | 0.0% | 0.0% | 0.0% |
| morceaux disjoints de l'union | 4 | 3.62 | 6 |
| cellules de la trame implicite | 78 | 78 | 121 |

## Réparation

| mode | budget | n | réparés | IC 95 % | t médian | déplacement médian |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` seul | — | 48 | **0.0 %** | [0.0, 7.4] | 3.6 ms | — |
| `pavage=True` | 0 | 48 | **0.0 %** | [0.0, 7.4] | 1.0 ms | — |
| `pavage=True` | 4 | 48 | **22.9 %** | [13.3, 36.5] | 1.5 ms | 5.56 m (53% du côté) |
| `pavage=True` | 8 | 48 | **54.2 %** | [40.3, 67.4] | 3.1 ms | 5.10 m (49% du côté) |
| `pavage=True` | 16 | 48 | **62.5 %** | [48.4, 74.8] | 3.6 ms | 5.51 m (53% du côté) |

## Échecs

{'base:invariant_viole': 48, 'pavage0:trame': 48, 'pavage4:trame': 37, 'pavage8:infaisable': 1, 'pavage16:infaisable': 2, 'pavage8:trame': 21, 'pavage16:trame': 16}

## Rejets à la construction

aucun
