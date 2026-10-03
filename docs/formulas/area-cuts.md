# Area cuts

**Code:** `lmo.cuts.area_cut`, `violated_areas`, `solve_with_areas`.

## Statement

The regulatory constraint \(w h \ge a_{\min}\) is **not** a linear
inequality. On \(\mathbb{R}_{>0}^2\), let \(g(w,h)=\log w+\log h\). \(g\) is
concave (Boyd & Vandenberghe, 2004, §3.1.5). Its superlevel sets

\[
K=\bigl\{(w,h):w>0,\; h>0,\; wh\ge a_{\min}\bigr\}
 =\bigl\{ g \ge \log a_{\min}\bigr\}
\]

are therefore **convex** (ibid., §3.1.6).

At the contact point \((w_0,h_0)\) of the hyperbola \(w_0 h_0=a_{\min}\),
\(\nabla g=(1/w_0,\,1/h_0)\) and the supporting half-space containing \(K\) reads

\[
\frac{w-w_0}{w_0}+\frac{h-h_0}{h_0}\ge 0
\quad\Longleftrightarrow\quad
h_0 w + w_0 h \ge 2 a_{\min}.
\]

## Derivation — gradient

Multiply \(\nabla g\cdot\bigl((w,h)-(w_0,h_0)\bigr)\ge 0\) by \(w_0 h_0>0\):

\[
h_0(w-w_0)+w_0(h-h_0)\ge 0
\implies
h_0 w + w_0 h \ge 2 w_0 h_0 = 2 a_{\min}.
\]

## Derivation — AM-GM (same inequality)

Hardy, Littlewood & P&oacute;lya (1952), theorem 16:

\[
\frac{1}{2}\Bigl(\frac{w}{w_0}+\frac{h}{h_0}\Bigr)
 \ge \sqrt{\frac{wh}{w_0 h_0}}.
\]

On the hyperbola \(w_0 h_0=a_{\min}\), the right-hand side is at least \(1\) as soon
as \(wh\ge a_{\min}\), hence \(h_0 w+w_0 h\ge 2 a_{\min}\). **No** point of
\(K\) is excluded. A point with a strictly smaller product may be.

## Projection before the tangent

If the current point violates \(wh<a_{\min}\), the tangent written *there* goes through a
point **inside the complement** of \(K\). It then cuts the hyperbola and
excludes admissible rectangles with the same aspect ratio.

We first project onto the hyperbola, keeping the ratio:

\[
(w_\star,h_\star)
 =\sqrt{\frac{a_{\min}}{wh}}\,(w,h).
\]

This is the code of `area_cut`.

## Why Kelley alone oscillates

The simplex only returns **vertices** of a polyhedron. \(K\) has a strictly
convex boundary: the optimum of \(\min(w+h)\) over \(K\) is the square
\((\sqrt{a},\sqrt{a})\) (AM-GM), which is a vertex of no finite
approximation. The vertices slide along a chord \(w+h=2\sqrt{a}\), with product
\(a-\delta^2\).

Kelley (1960) densifies the tangents. In addition, we **tighten the bounds**
\(w\ge w_\star\), \(h\ge h_\star\) (hyperbola–box intersection if the ray leaves the box)
then rerun GLOP, which readjusts \(x,y\). If this tightening makes the LP
infeasible (wrong aspect ratio), we **drop it** and keep cutting
— we do not declare the program infeasible.

Initial tangents: the square and the intersections of the hyperbola with
\(w=w_{\min}\), \(h=h_{\min}\), if they fit in the box of the bounds.

`MAX_CUTS_PER_ROOM = 10`: beyond it, `log.warning("coupe.limite", piece=...)`.

## Use cases

| Do | Do not |
|---|---|
| Call `solve_with_areas` from `legalize` (the regulation knows \(a_{\min}\)) | Put the loop in `lmo.solver.solve` — `lmo` ignores where \(c\) comes from **and** the room program |
| Project before writing the cut | Pass \(wh\ge a\) to GLOP as a product |
| Leave `a_min=0` without a cut | Believe that after 10 cuts the LP vertex is *on* the hyperbola: hence the tightening of bounds |

## Inner approximation, for Frank-Wolfe

Tangent cuts are an **outer** approximation of \(K = \{(w, h) : wh \ge a\}\): the
classic legalization uses them, then checks the result exactly. Frank-Wolfe cannot:
its iterates are convex combinations of a valid start and LP vertices, and a vertex of
an outer approximation may lie below the hyperbola, so the mix can break the minimum
area. That is what happened until 0.10 (AUDIT.md §3 n°6).

Frank-Wolfe therefore works on an **inner** approximation
(`lmo.cuts.inner_area_constraints`). Around the start \((w_0, h_0)\), take nodes
\(w_k = f_k w_0\), \(f_k = 1.1^k\) for \(k = -24, \dots, 24\) (about 0.10 to 9.85), and
\(h_k = a / w_k\). Nodes are not filtered by the variable bounds (the region is
intersected with them anyway): filtering froze rooms whose height a contact had fixed.
Keep

\[
w \ge w_{\text{first}}, \qquad h \ge \frac{a}{w_{\text{last}}}, \qquad
h \ge h_k + s_k (w - w_k) \quad \text{for each chord } [w_k, w_{k+1}],
\quad s_k = \frac{h_{k+1} - h_k}{w_{k+1} - w_k}.
\]

**Soundness.** \(h = a/w\) is convex on \(w > 0\), so it lies below each of its chords:
on \([w_{\text{first}}, w_{\text{last}}]\) the piecewise-linear interpolant \(\ell\)
satisfies \(\ell(w) \ge a/w\). \(\ell\) is convex (interpolant of a convex function),
hence equal to the maximum of its extended chords, so the chord rows describe exactly
its epigraph. Beyond \(w_{\text{last}}\), \(h \ge a/w_{\text{last}} > a/w\). The kept
region is a convex polyhedron included in \(K\): every point of the domain, and every
convex combination of such points, keeps the minimum area.

**The start stays admissible**, since \(w_0\) is a node: the rows only require
\(h_0 \ge a/w_0\).

**Cost of the approximation.** Between two nodes of ratio \(r = w_{k+1}/w_k\), the
chord asks for at most \(\frac{(r-1)^2}{4r}\) more area than the minimum (maximum of
\(w\,\ell(w)/a - 1\), reached at the midpoint \((w_k + w_{k+1})/2\) of the nodes). With
\(r = 1.1\) everywhere this is a uniform +0.23 %. The other price is the spread: a room's
width stays between about 0.10 and 9.85 times its start.

Measured effect on optimization, 200 benchmark scenarios, against a reference grid of
235 nodes (ratio 1.02): the default grid reaches a median 0.9985 of the reference gain,
and at least 0.95 of it in 96 % of the scenarios, for +4 ms median per call. A coarser
grid (ratio 1.25, 13 nodes) reached 0.95 in only 81 % of them. The remaining outliers do
not decrease monotonically with finer grids: they come from the path Frank-Wolfe takes
on a non-concave objective, not from the approximation.

A single corner \(w \ge w_0, h \ge h_0\) would have been sound too, but it freezes the
shape of a room whose area is tight; the chords let it trade width for height.

Since Frank-Wolfe no longer needs tangent cuts, its LP calls keep the warm start
(the cuts used to disable it, AUDIT.md Q-C2).

## Source

- Boyd & Vandenberghe (2004), §3.1.5–3.1.6.
- Hardy, Littlewood & P&oacute;lya (1952), th. 16.
- Kelley (1960), *SIAM J.*, [doi:10.1137/0108053](https://doi.org/10.1137/0108053).

[Bibliography](sources.md).
