# Milestone 8: legalizing **actually generated** plans

HouseDiffusion (CVPR 2023), official weights `model250000.pt`, RPLAN, **1000 steps** without respacing. 320 plans, 1960 rooms. Scale 11.605 m/unit, matched to the MSD median area (79.0 m²).

**0 plan(s) out of 320 are valid before correction.**

## State of the generator outputs

| | median | mean | p95 |
|---|--:|--:|--:|
| rooms overlapped per room | 0.80 | 0.81 | 1.61 |
| gap share of the envelope | 28.6% | 29.9% | 48.7% |
| of which **interior** holes | 0.0% | 0.0% | 0.0% |
| disjoint fragments of the union | 4 | 3.75 | 6 |
| cells of the implicit grid | 80 | 81 | 132 |

## Repair

Regulation `min_width = 0.50 m`.

| mode | budget | n | repaired | 95 % CI | median t | median displacement |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` alone | — | 320 | **0.0 %** | [0.0, 1.2] | 3.0 ms | — |
| `tiling=True` | 0 | 320 | **0.6 %** | [0.2, 2.2] | 0.9 ms | 1.68 m (18% of the side) |
| `tiling=True` | 4 | 320 | **10.9 %** | [8.0, 14.8] | 1.4 ms | 3.72 m (36% of the side) |
| `tiling=True` | 8 | 320 | **18.4 %** | [14.6, 23.1] | 3.0 ms | 4.08 m (40% of the side) |
| `tiling=True` | 16 | 320 | **20.3 %** | [16.3, 25.1] | 3.6 ms | 4.35 m (43% of the side) |

## What a floor on the width costs, and what it buys

| `min_width` | n | valid | **of which no room crushed** | smallest side | median displacement |
|--:|--:|--:|--:|--:|--:|
| 0.00 m | 320 | 60.9 % [55.5, 66.1] | **19.1 %** [15.1, 23.7] | 0.000 m | 56% |
| 0.25 m | 320 | 20.3 % [16.3, 25.1] | **19.1 %** [15.1, 23.7] | 1.360 m | 43% |
| 0.50 m *(nominal)* | 320 | 20.3 % [16.3, 25.1] | **20.3 %** [16.3, 25.1] | 1.360 m | 43% |
| 1.00 m | 320 | 20.3 % [16.3, 25.1] | **20.3 %** [16.3, 25.1] | 1.360 m | 43% |
| 1.80 m | 320 | 20.3 % [16.3, 25.1] | **20.3 %** [16.3, 25.1] | 1.800 m | 43% |

## Repair by program size

| rooms | n | repaired (budget 16) | median cells |
|--:|--:|--:|--:|
| 4 | 40 | 25.0 % | 32 |
| 5 | 80 | 25.0 % | 56 |
| 6 | 40 | 30.0 % | 78 |
| 7 | 120 | 13.3 % | 99 |
| 8 | 40 | 17.5 % | 126 |

## Repair by access-graph topology

| topology | n | repaired (budget 16) | median gap | median overlap | median fragments |
|---|--:|--:|--:|--:|--:|
| `etoile` | 320 | 20.3 % | 28.6% | 0.80 | 4 |

## Failures

{'base:invariant_viole': 320, 'pavage0:trame': 318, 'pavage4:infaisable': 50, 'pavage8:infaisable': 114, 'pavage16:infaisable': 585, 'pavage4:trame': 235, 'pavage8:trame': 147, 'pavage16:trame': 560}

## Rejections at construction

none
