# Frank-Wolfe on the polytope

**Code:** `solve.frank_wolfe`.

## Statement

We maximize a surrogate \(f\) (concave or not) over the
[polytope](polytope-separe.md) \(P\):

\[
\max_{x\in P} f(x).
\]

At the iterate \(x_k\), the linear oracle is **the same LP** as the legalization:

\[
s_k\in\arg\max_{s\in P}\langle\nabla f(x_k),s\rangle
=\arg\min_{s\in P}\langle -\nabla f(x_k),s\rangle,
\]

that is `lmo.resoudre(poly, c=-gradient, depart=x_k)`. The standard step is
\(\gamma_k=\min\{2/(k+2),\gamma_{\max}\}\), halved while \(f\) decreases. The gap

\[
g_k=\langle\nabla f(x_k),s_k-x_k\rangle
\]

bounds \(f^\star-f(x_k)\) **when \(f\) is concave**.

**What the gap means here.** None of the shipped surrogates is concave: the analytic one
is a product of a bilinear term and a convex exponential (AUDIT.md §5.1). For a
non-concave \(f\) the gap is only a first-order **stationarity** measure (it vanishes at
stationary points, Lacoste-Julien 2016), never a bound on \(f^\star - f(x)\). The code
therefore reports:

- `gap` computed **at the returned point** (one extra LP when the run ends on
  `max_iter`), and \(+\infty\) whenever it is unknown (no LP succeeded, or the LP at
  the returned point failed), so that a failure never reads as "optimum reached";
  `Trace.final_gap` carries the same value;
- `status`, why the run stopped: `converged` (\(g \le\) `tol`), `line_search_failed`
  (no step along the direction improved \(f\)), `lp_not_optimal`, or `max_iter`.

## Assumptions

- \(x_0\in P\) (in practice: the L1 output of milestone 2).
- Every call passes `depart=x`: the GLOP model is reused (`ARCHITECTURE.md` §10).
- Iterates are convex combinations of vertices, hence in \(P\).
- A budget \(\Delta\) is the box \(\lVert x-\hat x\rVert_\infty\le\Delta\) around the
  **proposed** plan \(\hat x\), shared by the classic pass and Frank-Wolfe, so that it
  is spent once. Centring it on the L1 point \(x_0\) allowed up to \(2\Delta\) in total
  (measured: 0.55 m for \(\Delta = 0.3\) m). The box always contains \(x_0\), which
  meets the budget only up to the LP tolerance when the budget is saturated. The proof
  checks \(\max \lvert x - \hat x\rvert \le \Delta\); a budget too small for the plan
  raises `Infaisable`.
- After L1, `figer_contacts` turns saturated separations into equalities and pins
  \(x, y\) to saturated outline edges: Frank-Wolfe keeps a tiling (no gap between rooms)
  while moving interior partitions. Saturated minimum widths stay free: a narrow room
  can grow.

## Derivation

Frank-Wolfe (1956): move towards a vertex, with a decreasing step. The away steps of
Lacoste-Julien & Jaggi (2015) remove mass from the worst active vertex, which speeds
up convergence on faces.

The identity oracle = legalizer is the core of the project: one solver, two cost
vectors \(c\).

## Code

`frank_wolfe` → `FrankWolfeResult` (`x`, `value`, `gap`, `status`, `iterations`,
`trace`, `duals`). `Trace.iterates`, `Trace.values`, `Trace.status` and
`Trace.final_gap` serve the acceptance criteria (the French names `iteres`, `objectif`,
`ecarts` and the `Iteration` fields `valeur`, `pas` remain as deprecated aliases).

## Use

| Do | Do not |
|---|---|
| Plug in any `Substitut` | Import `light.analytique` from `solve` |
| Read `gap` with `status` as a stationarity diagnostic | Read `gap` as a bound on the optimum (no shipped surrogate is concave), or confuse it with a coverage \(1-\alpha\) |

## Source

Frank & Wolfe (1956), *An algorithm for quadratic programming*, Naval Research
Logistics Quarterly. Lacoste-Julien & Jaggi (2015), *On the Global Linear Convergence
of Frank-Wolfe Optimization Variants*, NeurIPS. Lacoste-Julien (2016), *Convergence
Rate of Frank-Wolfe for Non-Convex Objectives*, arXiv:1607.00345.
[Bibliography](sources.md).
