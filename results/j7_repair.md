# Milestone 7: repair of corrupted MSD plans

MSD corpus, 300 real apartments, 4796 corruptions,
root seed 17. Every corrupted plan goes through **both** modes; *fallback* is the
applicable strategy: try `tiling=True`, fall back on plain `legalize` if the grid is
not recoverable. **0.0 %** of the corrupted plans are valid before correction.


| Fault | n | `legalize` | `tiling=True` | fallback | 95 % CI | median t |
|---|--:|--:|--:|--:|:--:|--:|
| gap (`retrecir`) | 1196 | 10.0 % | 97.6 % | **98.0 %** | [97.0, 98.6] | 6.5 ms |
| undersized (`aplatir`) | 1200 | 4.8 % | 96.0 % | **96.3 %** | [95.1, 97.3] | 6.5 ms |
| overlap (`elargir`) | 1200 | 68.2 % | 90.3 % | **91.2 %** | [89.5, 92.7] | 6.5 ms |
| offset (`deplacer`) | 1200 | 60.8 % | 88.1 % | **90.0 %** | [88.2, 91.6] | 6.6 ms |
| **all faults** | 4796 | 35.9 % | 93.0 % | **93.9 %** | [93.2, 94.5] | 6.5 ms |

| amplitude 0.1 m | 1199 | 37.3 % | 96.3 % | **96.8 %** | [95.7, 97.7] | 6.4 ms |
| amplitude 0.25 m | 1200 | 37.8 % | 96.3 % | **96.9 %** | [95.8, 97.8] | 6.5 ms |
| amplitude 0.5 m | 1199 | 35.0 % | 92.0 % | **93.2 %** | [91.7, 94.5] | 6.5 ms |
| amplitude 1.0 m | 1198 | 33.6 % | 87.3 % | **88.6 %** | [86.6, 90.2] | 6.7 ms |

## Reading

Without the tiling constraint, the separations of the polytope are **inequalities**: a
plan with a gap is already the closest point to itself, the L1 optimum leaves it as is,
and the exact verification rejects it. Hence less than 10 % on gaps against 68 % on
overlaps.

`tiling=True` imposes the edge/line incidences of the recovered grid. Since the tiling
condition is **combinatorial** (it bears only on indices, never on coordinates), every
admissible point becomes an exact tiling: a gap can no longer be represented. The
system stays feasible by construction; no infeasible LP was observed.

Grid recovery combines two mechanisms without any threshold in metres: the absorption
of **orphan** lines (support < 2), then a **bounded repair** of the partition, which
grows or shrinks a room by one step as long as the cells involved are all missing, or
all in excess. Budget 4: beyond it, the fault is no longer a wrong dimension but an
order inconsistency, and `deduce_grid` refuses.

## Limits

These perturbations are **not** a model of the errors of any particular generator: they
reproduce the fault families reported in the literature, without calibrating their
frequencies. The table must be complemented by at least one public generator before
publication.

The repair can **absorb a missing room into its neighbour**: closing a gap means
enlarging someone. The plan then comes out with one room fewer than expected. A caller
who must preserve the program room by room passes `repair_budget=0`.
