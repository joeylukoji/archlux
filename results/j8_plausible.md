# Milestone 8: legalizing **actually generated** plans

HouseDiffusion (CVPR 2023), official weights `model250000.pt`, RPLAN, **1000 steps** without respacing. 320 plans, 1960 rooms. Scale 10.528 m/unit, matched to the MSD median area (79.0 m²).

**0 plan(s) out of 320 are valid before correction.**

## State of the generator outputs

| | median | mean | p95 |
|---|--:|--:|--:|
| rooms overlapped per room | 1.60 | 1.58 | 3.15 |
| gap share of the envelope | 24.7% | 25.1% | 46.6% |
| of which **interior** holes | 0.0% | 0.0% | 0.0% |
| disjoint fragments of the union | 2 | 2.38 | 4 |
| cells of the implicit grid | 64 | 70 | 130 |

## Repair

Regulation `min_width = 0.50 m`.

| mode | budget | n | repaired | 95 % CI | median t | median displacement |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` alone | — | 320 | **0.0 %** | [0.0, 1.2] | 2.9 ms | — |
| `tiling=True` | 0 | 320 | **0.6 %** | [0.2, 2.2] | 0.8 ms | 1.52 m (18% of the side) |
| `tiling=True` | 4 | 320 | **10.6 %** | [7.7, 14.5] | 1.4 ms | 3.82 m (41% of the side) |
| `tiling=True` | 8 | 320 | **16.6 %** | [12.9, 21.0] | 2.9 ms | 3.95 m (38% of the side) |
| `tiling=True` | 16 | 320 | **17.8 %** | [14.0, 22.4] | 3.3 ms | 3.95 m (38% of the side) |

## What a floor on the width costs, and what it buys

| `min_width` | n | valid | **of which no room crushed** | smallest side | median displacement |
|--:|--:|--:|--:|--:|--:|
| 0.00 m | 320 | 59.7 % [54.2, 64.9] | **13.8 %** [10.4, 18.0] | 0.000 m | 48% |
| 0.25 m | 320 | 17.8 % [14.0, 22.4] | **13.8 %** [10.4, 18.0] | 0.740 m | 38% |
| 0.50 m *(nominal)* | 320 | 17.8 % [14.0, 22.4] | **17.8 %** [14.0, 22.4] | 0.740 m | 38% |
| 1.00 m | 320 | 17.8 % [14.0, 22.4] | **17.8 %** [14.0, 22.4] | 1.000 m | 38% |
| 1.80 m | 320 | 17.8 % [14.0, 22.4] | **17.8 %** [14.0, 22.4] | 1.800 m | 38% |

## Repair by program size

| rooms | n | repaired (budget 16) | median cells |
|--:|--:|--:|--:|
| 4 | 40 | 25.0 % | 30 |
| 5 | 80 | 28.8 % | 49 |
| 6 | 40 | 20.0 % | 63 |
| 7 | 120 | 11.7 % | 81 |
| 8 | 40 | 5.0 % | 109 |

## Repair by access-graph topology

| topology | n | repaired (budget 16) | median gap | median overlap | median fragments |
|---|--:|--:|--:|--:|--:|
| `plausible` | 320 | 17.8 % | 24.7% | 1.60 | 2 |

## Failures

{'base:invariant_viole': 320, 'pavage0:trame': 318, 'pavage4:infaisable': 57, 'pavage8:infaisable': 121, 'pavage16:infaisable': 601, 'pavage4:trame': 229, 'pavage8:trame': 146, 'pavage16:trame': 580}

## Rejections at construction

none
