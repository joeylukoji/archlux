# Exact verification

**Code:** `certify.proof.verify_exactly`.

Independent of the solver: if GLOP has a bug, this inspection is what
shows it (`ARCHITECTURE.md`: never trust the solver).

## Statement

Four predicates, conjoined into `valid`. **None of them is probabilistic.**

\[
\mathrm{valid}
 = \neg\mathrm{overlap}
 \land \neg\mathrm{gaps}
 \land \mathrm{areas\_ok}
 \land \mathrm{structure\_kept}.
\]

### Overlap

For each pair of rectangles \(R_i,R_j\), intersection area
\(\lambda(R_i\cap R_j)\) (GEOS / Shapely, Vatti clipping, 1992). Overlap
iff this area exceeds `OVERLAP_M2` \(=10^{-9}\,\mathrm{m}^2\). Message:
`"overlap kitchen|bathroom: 0.0300 m²"`. Complexity \(O(n^2)\) pairs, accepted. This GEOS
path now only serves non-rectangular outlines; a rectangular outline goes
through the rational proof below.

### Gaps

Let \(U=\bigcup_i R_i\) and \(C\) the outline polygon. A gap exists iff

\[
\bigl\lvert \lambda(U)-\lambda(C)\bigr\rvert > \tau,
\qquad \tau=10^{-6}\,\mathrm{m}^2.
\]

An exact tiling satisfies \(\lambda(U)=\lambda(C)\) and \(\lambda(R_i\cap R_j)=0\)
for \(i\neq j\) (Lebesgue additivity over a disjoint union, Halmos, 1950).

This test is stronger than "no interior hole": a plan that does not *fill*
the envelope is rejected. [L1](l1-epigraph.md) does not force filling;
`legalize` only promises a tiling if the input already is one (slicing) or if
the union of the rooms covers \(C\) (an overlap to correct without creating a gap).

### Areas

\[
w_p h_p \ge a_{\min}(\mathrm{type}(p))
\]

for each room, up to \(10^{-9}\,\mathrm{m}^2\). \(a_{\min}=0\) if the type
is unknown (`Regulation.min_area`).

**Fused rooms** (an L decomposed into sub-rectangles, `verify_exactly(..., merges=)`).
The minimum applies to the union \(U = \bigcup_k R_k\) of the parts, never to each
part: \(\lambda(U) \ge a_{\min}\). Before the area, every seam recorded by the
decomposition must still hold: the two parts touch along it (offset at most
`SNAP_M`) over a length of at least `min_width` (minus `SNAP_M`), the contact the
solver imposes (`geom.rectilinear.overlap_constraints`). Connectivity alone would
accept a foot that slid to another edge, or a neck of \(10^{-7}\) m. Parts that do not
form one polygon through edges (detached, or touching at a corner) are refused.

### Structure

No room crosses a load-bearing wall of `ctx.structure`: for every wall segment
\(S\) and room \(R\),

\[
\operatorname{length}\bigl(S \cap \operatorname{int}_{\varepsilon}(R)\bigr) \le \varepsilon,
\qquad \varepsilon = 10^{-7}\,\mathrm{m},
\]

where \(\operatorname{int}_{\varepsilon}(R)\) is the room shrunk by \(\varepsilon\) on every
side, so that a room *bounded* by the wall is accepted. A fused room is one interior,
\(\operatorname{int}_{\varepsilon}(\bigcup_k R_k)\): a wall along the seam between two
parts cuts the room in two and is a crossing, although it is on the boundary of each
part. The test is geometric and holds for oblique walls. A wall declared in the plan with the same `id` must also match the
structure (same end points, order irrelevant). Columns are not checked.

*Before 0.10 this predicate only compared each wall with itself (walls are not decision
variables), so it was always true (AUDIT.md §3 n°1).*

### Displacement

\(\ell_\infty\) norm over the four dimensions, max over the rooms with the same `id`:

\[
\delta_\infty
 =\max_p \max\bigl(\lvert\Delta x\rvert,\lvert\Delta y\rvert,
 \lvert\Delta w\rvert,\lvert\Delta h\rvert\bigr)
 \quad[\mathrm{m}].
\]

`reference=None` returns \(0\).

## Exact rational proof of the tiling (rectangular outlines)

Since batch 1.5b, when the outline is an axis-aligned rectangle \(C\), overlaps and
gaps are no longer decided by GEOS areas with tolerances, but proved in exact rational
arithmetic (`certify.proof.rational_tiling`):

1. **Identification.** Edge coordinates closer than \(\varepsilon = 10^{-7}\) m
   (`SNAP_M`) are identified, each group being anchored on its smallest value. This is
   the **only** tolerance: it applies to lengths, whatever the size of the rooms, and
   absorbs both decimal inputs (\(0.1 + 0.2 \ne 0.3\) in binary floating point) and the
   LP noise.
2. **Exact check.** Every coordinate is then an exact `Fraction` (a binary float is an
   exact rational) and three conditions are tested with no tolerance: (i) every room
   lies in \(C\); (ii) the interiors of any two rooms are disjoint; (iii)
   \(\sum_i \lambda(R_i) = \lambda(C)\).

**Theorem.** (i) and (ii) give
\(\lambda(\bigcup_i R_i) = \sum_i \lambda(R_i) \le \lambda(C)\); with (iii), the part of
\(C\) left uncovered has measure \(\lambda(C) - \sum_i \lambda(R_i) = 0\). The rooms tile
\(C\) up to a null set: no gap, no overlap.

When rooms overlap, (iii) no longer measures coverage; the gap diagnosis then comes from
GEOS, so that the report stays complete (the plan is invalid either way). Outlines that
are not rectangles keep the GEOS area checks and their tolerances.

**What the identification erases.** The theorem is about the *identified* rectangles.
Moving edges by less than \(\varepsilon = \) `SNAP_M` can hide up to \(\varepsilon\) times a
perimeter of area (9e-6 m² along a 100 m edge), more than the checker tolerance. Once
the identified tiling is proved, the raw plan is therefore bounded too, still in exact
arithmetic: every raw pairwise overlap \(\lambda(R_i \cap R_j) \le\) `OVERLAP_M2`; the
overhang \(\sum_i \lambda(R_i) - \lambda(R_i \cap C) \le\) `GAP_M2`; and, by Bonferroni's
inequality \(\lambda(\bigcup_i R_i \cap C) \ge \sum_i \lambda(R_i \cap C) - \sum_{i<j}
\lambda(R_i \cap R_j \cap C)\), the uncovered area is at most
\(\lambda(C) - \sum_i \lambda(R_i \cap C) + \sum_{i<j} \lambda(R_i \cap R_j \cap C) \le\)
`GAP_M2`. These are the tolerances of the GEOS path and of the test checker, so the two
paths agree on every plan, not only on the benchmark (review of batch 1.5, M2).

**Measured agreement.** On the plans of the guarantee benchmark (valid, corrupted, noisy
and legalized), the rational proof and the GEOS check give identical overlap and gap
verdicts. The certification of 15 rooms takes about 0.8 ms (1.5 ms with GEOS).

## Use cases

| Do | Do not |
|---|---|
| Call it *after* the solver, on the devectorized plan | Reuse the duals or `poly.contains` as a user-facing proof |
| Report **all** the violations | Stop at the first one |
| Put a probability field in `GeometricProof` | — forbidden: the project's thesis lives in this type |

## Source

- Vatti (1992), *CACM* — clipping, [doi:10.1145/129902.129906](https://doi.org/10.1145/129902.129906).
- Halmos (1950), *Measure Theory* — additivity.
- The \(\lVert\cdot\rVert_\infty\) norm is the usual definition; not a theorem.

[Bibliography](sources.md).
