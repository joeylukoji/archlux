# Milestone 8: legalizing **actually generated** plans

HouseDiffusion (CVPR 2023), official weights `model250000.pt`, RPLAN, **1000 steps** without respacing. 48 plans, 294 rooms. Scale 11.661 m/unit, matched to the MSD median area (79.0 m²).

**0 plan(s) out of 48 are valid before correction.**

## State of the generator outputs

| | median | mean | p95 |
|---|--:|--:|--:|
| rooms overlapped per room | 0.80 | 0.84 | 1.64 |
| gap share of the envelope | 26.6% | 28.3% | 44.9% |
| of which **interior** holes | 0.0% | 0.0% | 0.0% |
| disjoint fragments of the union | 4 | 3.62 | 6 |
| cells of the implicit grid | 78 | 78 | 121 |

## Repair

| mode | budget | n | repaired | 95 % CI | median t | median displacement |
|---|--:|--:|--:|:--:|--:|--:|
| `legalize` alone | — | 48 | **0.0 %** | [0.0, 7.4] | 3.6 ms | — |
| `tiling=True` | 0 | 48 | **0.0 %** | [0.0, 7.4] | 1.0 ms | — |
| `tiling=True` | 4 | 48 | **22.9 %** | [13.3, 36.5] | 1.5 ms | 5.56 m (53% of the side) |
| `tiling=True` | 8 | 48 | **54.2 %** | [40.3, 67.4] | 3.1 ms | 5.10 m (49% of the side) |
| `tiling=True` | 16 | 48 | **62.5 %** | [48.4, 74.8] | 3.6 ms | 5.51 m (53% of the side) |

## Failures

{'base:invariant_viole': 48, 'pavage0:trame': 48, 'pavage4:trame': 37, 'pavage8:infaisable': 1, 'pavage16:infaisable': 2, 'pavage8:trame': 21, 'pavage16:trame': 16}

## Rejections at construction

none
