
# Polytope of the separations

**Code:** `geom.polytope.build_polytope`, `Polytope.contains`, `vectorize`,
`devectorize`.

## Statement

Four variables per room, in this order: \(x,y,w,h\). The index
`"<id>.x"` is a contract: a trace of duals can only be read back if the columns
do not move.

For each horizontal edge \(a\to b\) of the *reduced* graph:

\[
x_a + w_a - x_b \le 0.
\]

Vertically: \(y_a + h_a - y_b \le 0\). The rectangular envelope
\([x_{\min},x_{\max}]\times[y_{\min},y_{\max}]\) adds

\[
x_i + w_i \le x_{\max},\qquad y_i + h_i \le y_{\max}.
\]

The bottom / left edges and the minimum widths \(\ell_{\min}\) go through
**`bounds`**, not through \(A\): \(w_i,h_i\in[\ell_{\min}, L]\) where \(L\) is the side
of the envelope.

The set \(\{x : Ax\le b,\; \ell\le x\le u\}\) is a **polyhedron** (Boyd &
Vandenberghe, 2004, §2.2.4).

## Assumptions

- Fixed relative order (otherwise the domain of valid plans is **not** convex:
  one can go around \(B\) by two paths whose segment is not admissible).
- Graph transitively reduced *before* assembly.
- Load-bearing walls are fixed obstacles. Each room keeps the side of each wall it
  had in the proposed plan (`RelativeOrder.wall_sides`): one inequality per room and
  wall, \(x + w \le c\) (left), \(x \ge c\) (right), \(y + h \le c\) (below) or
  \(y \ge c\) (above), where \(c\) is the wall line or the end of a partial wall.
  The half-plane kept is the one the proposed room penetrates **least**, among those
  with room left before the outline: for a room clear of the wall this is the axis of
  the largest gap (the rule between two rooms); for a room crossing it, the smallest
  correction, which may go around the end of a partial wall. Zero-length walls are
  ignored; oblique load-bearing walls are refused (`UnsupportedInput`).
  \(A_{\mathrm{eq}}\) stays empty.
- **Deliberate over-constraint.** A room beyond the end of a partial wall could also
  be kept off it by another half-plane; only one is kept, so Frank-Wolfe cannot move
  the room from one valid side to another. This is the price of convexity, exactly as
  for the relative order between two rooms: safe, never a false certificate, but it
  restricts the search.

## What is not in \(A\)

\(w h \ge a_{\min}\) is not linear. Defer it to the
[area cuts](area-cuts.md). Writing it as is in GLOP is a modelling
error, not an implementation detail.

## Use cases

| Do | Do not |
|---|---|
| `contains(x)` as an oracle **independent** of the solver | Trust `status == "optimal"` without `contains` or `verify_exactly` |
| Keep `origins[i]` = label of row \(i\) of \(A\) | Number the duals by bare row index |
| Vectorize / devectorize through `index` | Store glazing in absolute coordinates (it gets out of sync with its wall) |

`Polytope.contains` is deliberately naive: \(Ax \le b+\varepsilon\), equalities,
bounds. It is the one that catches a simplex bug.

## Source

- Boyd & Vandenberghe (2004), §2.2.4 — polyhedra.
- Lengauer (1990), ch. 10 — compaction.
- Otten (1982) — slicing floorplans, which are points of this polytope.

[Bibliography](sources.md).
