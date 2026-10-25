# Relative order and constraint graph

**Code:** `geom.graph.deduce_order`, `build_graph`, `transitive_reduction`.

## Statement

For two rectangles \(A,B\), the *clearance* on the \(x\) axis is

\[
\delta_x(A,B)=\max\bigl(x_B-(x_A+w_A),\; x_A-(x_B+w_B)\bigr).
\]

\(\delta_x>0\): the projections on \(x\) are disjoint; \(\delta_x=0\): they
touch; \(\delta_x<0\): they overlap. Likewise \(\delta_y\) vertically.

**Founding rule.** Every pair receives **exactly one** edge, on the axis where the
rooms are actually disjoint (the larger clearance if both are). When both
clearances are negative (overlap), the axis of the larger distance between *centers*
decides. The *direction* of the edge follows the total order \((\text{center}, \mathrm{id})\).

A horizontal edge \(A\to B\) reads "\(A\) is left of \(B\)" and will become

\[
x_A+w_A\le x_B.
\]

## Assumptions

- Rectangular rooms, sides parallel to the axes.
- Comparable identifiers (lexicographic order) to break ties between centers.
- Contact tolerance \(\tau=10^{-9}\,\mathrm{m}\): \(\delta\ge -\tau\) counts as
  disjoint. Without it, \(1+3.47=4.470000000000001\) in IEEE-754 makes two
  adjoining rooms look overlapping.

## Derivation — acyclicity

On a fixed axis, the edge always goes from the smaller center to the larger one (up to
\(\mathrm{id}\)). The set of edges of one axis is therefore a subgraph of a
**total order**, hence a DAG. A cycle "\(A\) left of \(B\) left of \(A\)"
is impossible *by construction* of `deduce_order`. `build_graph` checks it again
(`networkx.is_directed_acyclic_graph`) in case the order comes from elsewhere.

## Derivation — transitive reduction

If \(A\to B\) and \(B\to C\), then \(x_A+w_A\le x_B\) and \(x_B+w_B\le x_C\). Since
\(w_B\ge 0\), \(x_A+w_A\le x_C\): the edge \(A\to C\) is *implied*. The transitive
reduction (Aho, Garey & Ullman, 1972) removes these edges without changing the order
closure. 15 rooms: \(\sim 210\) raw constraints, \(\sim 30\) after reduction.

`networkx.transitive_reduction` drops isolated nodes; they are **put back**:
a room separated only on the other axis would disappear, and the polytope would lose
its bounds.

## Scope: one fixed topology

**How the constraint sequence is generated.** Once, from the **proposed** plan, by
`deduce_order` (and `WallSide` for load-bearing walls, the seams of fused rooms for
`merges=`, the grid of `deduce_grid` with `tiling=True`). It is never regenerated
during the solve: the classic L1 pass and Frank-Wolfe both work inside the polytope of
that one order, and Frank-Wolfe additionally freezes the contacts the L1 pass saturated
(`freeze_contacts`).

**What it can represent.** Every plan that keeps, for every pair of rooms, the side of
the edge chosen above ("\(A\) left of \(B\)", "\(A\) below \(B\)"), every room on its side
of every load-bearing wall, and (with `merges=`) the cut order of every fused room.
Inside that set, the solver changes **dimensions and positions only**.

**What it cannot represent.** Anything that changes the topology: swapping two rooms,
moving a room from the left of another to above it, creating or removing an adjacency
the order forbids, adding, deleting, merging or splitting a room, turning an L into a
Z, or moving a room across a load-bearing wall. The method is a legalization of the
generator's topology, not a layout search: a plan whose defect can only be removed by
a topological change is outside its reach, by construction.

**How infeasibility is detected, and what it means.** A refusal is always typed,
never a silent best effort:

| Exception | Detected by | Means |
|---|---|---|
| `InconsistentOrder` | a cycle in the constraint graph (`build_graph`) | the order itself is contradictory |
| `MissingSeparation` | a pair without any edge | the order does not separate two rooms |
| `Infeasible` with a Farkas certificate | the L1 LP (`lmo.solver.solve`), certificate verified exactly | **for this order**, the program does not fit the envelope; another order might |
| `Infeasible` from `restrict_to_budget` | the budget box misses a variable's bounds | the displacement budget is too small for this plan |
| `GapNeedsTiling` | the exact proof finds only a gap | rerun with `tiling=True` |
| `GridNotRecoverable` | `deduce_grid` | the rooms do not fall into the cells of a grid |

A Farkas certificate proves infeasibility **of the polytope of the proposed order**,
not of the room program: it does not say that no valid plan exists, only that none
exists with that topology.

## Use cases

| Do | Do not |
|---|---|
| Read the order of a *proposed* plan (the generator decides) | Pick the axis of the larger distance between centers while the rooms overlap on that axis — the constraint produced is already violated by a correct plan |
| Reduce before assembling \(A x\le b\) | Test `has_separation` *after* reduction: a pair separated by transitivity no longer has a direct edge |
| Tolerate contact at \(10^{-9}\,\mathrm{m}\) | Handle edges as a `set`: the iteration order would change the rows of \(A\) |

## Source

- Otten (1982), DAC — slicing floorplans, order of cuts.
- Lengauer (1990), ch. 10 — constraint graph \(x_a+w_a\le x_b\).
- Aho, Garey & Ullman (1972), *SIAM J. Comput.* — transitive reduction,
  [doi:10.1137/0201008](https://doi.org/10.1137/0201008).

Details of the editions: [bibliography](sources.md).
