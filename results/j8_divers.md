# Milestone 8: legalizing **actually generated** plans

HouseDiffusion (CVPR 2023), official weights `model250000.pt`, RPLAN, **1000 steps** without respacing. 100 plans, 588 rooms. Scale 11.566 m/unit, matched to the MSD median area (79.0 m²).

**0 plan(s) out of 100 are valid before correction.**

## State of the generator outputs

| | median | mean | p95 |
|---|--:|--:|--:|
| rooms overlapped per room | 1.00 | 1.10 | 2.01 |
| gap share of the envelope | 28.7% | 29.5% | 51.9% |
| of which **interior** holes | 0.0% | 0.0% | 0.0% |
| disjoint fragments of the union | 3 | 2.89 | 5 |
| cells of the implicit grid | 64 | 73 | 156 |

## Repair

Regulation `min_width = 0.50 m`.

| mode | budget | n | repaired | 95 % CI | median t | median displacement |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` alone | — | 100 | **0.0 %** | [0.0, 3.7] | 2.7 ms | — |
| `tiling=True` | 0 | 100 | **3.0 %** | [1.0, 8.5] | 0.8 ms | 3.61 m (43% of the side) |
| `tiling=True` | 4 | 100 | **17.0 %** | [10.9, 25.5] | 1.4 ms | 3.98 m (43% of the side) |
| `tiling=True` | 8 | 100 | **23.0 %** | [15.8, 32.2] | 2.5 ms | 3.98 m (43% of the side) |
| `tiling=True` | 16 | 100 | **23.0 %** | [15.8, 32.2] | 2.9 ms | 3.98 m (43% of the side) |

## What a floor on the width costs, and what it buys

| `min_width` | n | valid | **of which no room crushed** | smallest side | median displacement |
|--:|--:|--:|--:|--:|--:|
| 0.00 m | 100 | 59.0 % [49.2, 68.1] | **20.0 %** [13.3, 28.9] | 0.000 m | 51% |
| 0.25 m | 100 | 23.0 % [15.8, 32.2] | **20.0 %** [13.3, 28.9] | 1.084 m | 43% |
| 0.50 m *(nominal)* | 100 | 23.0 % [15.8, 32.2] | **23.0 %** [15.8, 32.2] | 1.084 m | 43% |
| 1.00 m | 100 | 23.0 % [15.8, 32.2] | **23.0 %** [15.8, 32.2] | 1.084 m | 43% |
| 1.80 m | 100 | 22.0 % [15.0, 31.1] | **22.0 %** [15.0, 31.1] | 1.800 m | 44% |

## Repair by program size

| rooms | n | repaired (budget 16) | median cells |
|--:|--:|--:|--:|
| 3 | 12 | 33.3 % | 16 |
| 4 | 16 | 37.5 % | 36 |
| 5 | 20 | 35.0 % | 48 |
| 6 | 16 | 25.0 % | 80 |
| 7 | 12 | 16.7 % | 87 |
| 8 | 12 | 0.0 % | 126 |
| 9 | 8 | 0.0 % | 131 |
| 10 | 4 | 0.0 % | 181 |

## Repair by access-graph topology

| topology | n | repaired (budget 16) | median gap | median overlap | median fragments |
|---|--:|--:|--:|--:|--:|
| `anneau` | 24 | 37.5 % | 28.5% | 1.00 | 3 |
| `chaine` | 24 | 8.3 % | 27.9% | 1.42 | 2 |
| `etoile` | 28 | 25.0 % | 29.2% | 0.93 | 4 |
| `plausible` | 24 | 20.8 % | 32.1% | 0.93 | 3 |

## Failures

{'base:invariant_viole': 100, 'pavage0:trame': 97, 'pavage4:trame': 69, 'pavage8:trame': 49, 'pavage16:trame': 190, 'pavage4:infaisable': 14, 'pavage8:infaisable': 28, 'pavage16:infaisable': 160}

## Rejections at construction

none
