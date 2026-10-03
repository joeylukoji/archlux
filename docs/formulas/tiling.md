# Exact tiling

**Code:** `geom.grid.deduce_grid` (re-exported by `geom.tiling`), `extend_tiling`; `api.legalize(..., tiling=True)`.

## The problem

The [order polytope](separated-polytope.md) is a **relaxation**: \(x_a+w_a\le x_b\)
forbids overlap, never a hole. If the input carries a gap, the plan with the hole
is already the point closest to itself: the optimum of
[the L1 epigraph](l1-epigraph.md) leaves it as is, and
[the exact verification](exact-proof.md) rejects it.

Measured on MSD: `legalize` repairs 68.2 % of overlaps and **10.0 %** of gaps.

## Statement

In a rectangular dissection, every room edge lies on a **grid
line**. Let \(v_0<\dots<v_p\) be the vertical lines, \(h_0<\dots<h_q\) the
horizontal ones. Room \(i\) reads

\[
R_i=[\,v_{l(i)},\,v_{r(i)}\,]\times[\,h_{b(i)},\,h_{t(i)}\,],
\qquad l(i)<r(i),\; b(i)<t(i),
\]

and covers exactly the **cells** \(C_{\alpha\beta}=[v_\alpha,v_{\alpha+1}]\times
[h_\beta,h_{\beta+1}]\) such that \(l(i)\le\alpha<r(i)\) and \(b(i)\le\beta<t(i)\).

> **Proposition.** Let \(\mathcal{K}\) be the set of cells inside the
> outline. If the families \(\{(\alpha,\beta)\}_i\) form a **partition** of
> \(\mathcal{K}\), then for *any* strictly increasing sequences
> \((v_\alpha)\), \((h_\beta)\), the union of the \(R_i\) tiles the outline exactly.

*Proof.* The cells have pairwise disjoint interiors and their
union is the outline. Each \(R_i\) is the union of the cells of its family. A
partition of the families therefore gives
\(\lambda(\bigcup_i R_i)=\sum_i\lambda(R_i)=\lambda(\mathcal{K})\) and
\(\lambda(R_i\cap R_j)=0\) for \(i\neq j\) (additivity, Halmos 1950). ∎

**The tiling condition bears only on the indices, never on the
coordinates.** It is a combinatorial fact, checked once and for all.

It is then enough to impose *"these edges share a line"*, that is affine
equalities in the existing variables:

\[
x_i = x_j \quad\text{or}\quad x_i = x_j + w_j
\quad\text{depending on the side},
\]

and to **pin** the lines carrying a vertex of the outline, which is input
data. Every admissible point is then an exact tiling: **a gap can no longer
be represented**.

## Assumptions

- The outline is **rectilinear**, and all its vertices enter the grid:
  otherwise a cell would straddle the boundary and the mask would make no sense.
- The partition bears on the cells **inside the outline**. Requiring a tiling
  of the bounding box would reject every L-shaped apartment.
- Strict increase of the lines is not imposed: it follows from the
  separations and from \(w\ge 0\). Two lines may coincide, crushing a room;
  the L1 objective avoids it in practice, `min_width > 0` forbids it.

## Recovering the grid from a faulty plan

The grid must be read on the **proposed** plan, which is precisely invalid.

A metric tolerance **does not work**: too wide, it crushes narrow
partitions; too narrow, it recovers nothing. Measured: 3.8 % repaired.

The right criterion is the **support** of a line — the number of edges it carries.
In a sound plan, an interior line carries at least two: a wall separates
two rooms. Moving a room makes one edge leave its line and creates a
new one, carried by that edge alone. We therefore absorb the **orphan** lines
(support \(<2\)) into their nearest neighbour, refusing any merge that
would crush a room.

No threshold in metres is involved: a gap of \(2\,\mathrm{m}\) is recovered
as well as a gap of \(5\,\mathrm{cm}\), and a partition of \(40\,\mathrm{cm}\)
survives.

**Bounded repair.** After consolidation, *local* defects remain: a
cell left uncovered, or covered twice — the dominant case on MSD. We then grow
or shrink a room **by one step**, which keeps it rectangular by
construction. An extension is kept only if **all** the cells gained
are missing; a reduction, only if all those released are in excess. Nothing
is invented: a room gets back what a fault had taken from it.

The budget (default 4) is what tells a repair from a reconstruction. It
saturates quickly — 8 gains nothing over 4:

| budget | 0 | 2 | 4 | 8 |
|---|--:|--:|--:|--:|
| grid recovered | 77.8 % | 98.5 % | **99.2 %** | 99.2 % |

!!! warning "Semantic consequence"
    Closing a gap means enlarging someone: the repair can **absorb a
    missing room into its neighbour**, and the plan comes out with one room fewer than
    the generator had planned. A caller who must preserve the room program
    room by room passes ``repair_budget=0`` — the partition is then checked,
    never touched up.

## Two properties

1. **The system stays feasible.** The grid positions of the reference plan are
   always an admissible point. Freezing *approximately* saturated contacts
   (`freeze_contacts`) offers no guarantee of this kind: 8 % infeasible LPs
   measured, for only 41.5 % repaired.
2. **The guarantee is structural.** It depends on no tolerance at
   run time: the partition check has already taken place.

## Results

4,796 corruptions of 300 real MSD apartments; raw data and table in
`results/j7_repair_raw.csv` and `results/j7_repair.md`:

| Fault | `legalize` | `tiling=True` | fallback |
|---|--:|--:|--:|
| gap | 10.0 % | 97.6 % | **98.0 %** |
| undersize | 4.8 % | 96.0 % | **96.3 %** |
| overlap | 68.2 % | 90.3 % | **91.2 %** |
| shift | 60.8 % | 88.1 % | **90.0 %** |
| **all** | 35.9 % | 93.0 % | **93.9 %** |

95 % CI on the overall fallback: [93.2 – 94.5]. Median time 6.5 ms, under the budget of
20 ms of `ARCHITECTURE.md` §9. By fault amplitude: 96.8 % at 10 cm, 96.9 % at
25 cm, 93.2 % at 50 cm, 88.6 % at 1 m.

The fallback adds only one point: the tiling constraint dominates almost everywhere
on its own. It remains useful where the corruption destroys the combinatorial structure —
`deduce_grid` then refuses rather than guess, and L1 alone takes over.

## Use cases

| Do | Do not |
|---|---|
| Enable it as soon as the input may carry a gap (generator output) | Enable it on an input of unknown structure without planning the fallback |
| Read the diagnostic: it names the faulty cells | Widen the tolerance to "get it through" — it is not the lever |
| Keep the fallback on `legalize` alone | Believe that tiling dominates everywhere |

## Source

Wall-coordinate formulation of rectangular dissections:
Otten (1982), [bibliography](sources.md) no. 6; Lengauer (1990) ch. 10, no. 7.
Additivity: Halmos (1950), no. 10.
