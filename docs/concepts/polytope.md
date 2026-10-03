# The polytope of valid plans

A fixed relative order (A left of B, C below D) turns legalization into a
**linear program**. Without that order, the domain of valid plans is not convex:
A can slide around B along two paths whose connecting segment is not feasible.

## Formula

Four variables per room: `(x, y, w, h)`. For each horizontal edge `a → b` of the order
graph (Otten, *Automatic Floorplan Design*, DAC 1982, slicing floorplans; compaction by
constraint graph, Lengauer, *Combinatorial Algorithms for Integrated Circuit Layout*,
Teubner, 1990, ch. 10):

```
x_a + w_a ≤ x_b
```

Likewise vertically: `y_a + h_a ≤ y_b`. The envelope adds `x + w ≤ X_max` and
`y + h ≤ Y_max`. Minimum widths are bounds, not rows of `A`.

The set of `x` that satisfy `A x ≤ b` is a **polyhedron** (Boyd & Vandenberghe,
*Convex Optimization*, Cambridge University Press, 2004, §2.2.4). Every point of this
polyhedron is a plan without overlap, for the fixed relative order.

## What is not linear

The area `w h ≥ a_min` is not a linear inequality. The set
`{(w,h) > 0 : w h ≥ a_min}` is nevertheless **convex**: it is a superlevel set of
`log w + log h`, which is concave (Boyd & Vandenberghe, §3.1.5–3.1.6). It is replaced
by its tangents (Kelley, *SIAM J.* 8, 1960):

```
h₀ w + w₀ h ≥ 2 a_min
```

at the point of the hyperbola `w₀ h₀ = a_min`. This is also AM-GM (Hardy, Littlewood,
Pólya, *Inequalities*, 2nd ed., Cambridge, 1952, theorem 16).

## Distance to the proposed plan

Minimizing `Σ |x_i − x̂_i|` is not linear. The epigraph (Bertsimas & Tsitsiklis,
*Introduction to Linear Optimization*, Athena Scientific, 1997, §1.3) introduces
`e_i ≥ |x_i − x̂_i|` and minimizes `Σ e_i`. The `x̂_i` enter the **constraints**,
never the cost vector `c = (0, …, 0, 1, …, 1)`.

## Verification

The solver is not trusted. `certify.proof` recounts intersection areas (Shapely /
GEOS), the area gap between union and outline, room areas and load-bearing walls.
`valid` is the conjunction of four booleans, none of them probabilistic.

**See also:** [Repair a plan](../gallery/01-repair-a-plan.md),
[The two guarantees](two-guarantees.md),
[formula book — polytope](../formulas/separated-polytope.md),
[formula book — L1](../formulas/l1-epigraph.md),
[formula book — cuts](../formulas/area-cuts.md).
