# Rectilinear decomposition

**Code:** `geom.rectilinear.decompose` / `recompose` / `extend_merges`.

## Statement

A simple **rectilinear** polygon (only horizontal or vertical edges)
admits a partition into rectangles. **Fixed** convention (`MILESTONE-6.md`):

1. among the reflex vertices, consider the interior **vertical cuts**;
2. pick the one with the smallest abscissa (left first); on a tie, smallest ordinate;
3. recurse until only rectangles remain (at most 4).

The rectangles that belong to the same domain room are linked by **merges**:

\[
x_i + w_i = x_j
\quad\text{(shares\_right\_edge)},\qquad
y_i + h_i = y_j
\quad\text{(shares\_top\_edge)}.
\]

These equalities enter \(A_{\mathrm{eq}}\) through `extend_merges`; the polytope
stays linear.

## Assumptions

- Simple, valid polygon, without holes.
- Axis-aligned edges.
- The decomposition of an L is not unique in general: **without the convention
  above, the results are not reproducible.**

## Code

| Symbol | Function |
|---|---|
| partition | `decompose` |
| union | `recompose` |
| \(A_{\mathrm{eq}}\) | `extend_merges` → `legalize(..., merges=)` |

## Use cases

| Do | Do not |
|---|---|
| Split, then pass the sub-rectangles as `Room` | Store a raw L polygon in `Plan.rooms` |
| Fix the vertical-left convention | Change the cut order depending on the input |
| Budget < 40 ms for 15 rooms of which 4 are L-shaped | Over-fine decomposition (cell grid) |

## Source

Project convention (`MILESTONE-6.md` §2); classic slicing partition.
