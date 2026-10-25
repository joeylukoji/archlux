# Frank-Wolfe on the polytope

**Code:** `solve.frank_wolfe`.

## Statement

We maximize a surrogate \(f\) (concave or not) over the
[polytope](separated-polytope.md) \(P\):

\[
\max_{x\in P} f(x).
\]

At the iterate \(x_k\), the linear oracle is **the same LP** as the legalization:

\[
s_k\in\arg\max_{s\in P}\langle\nabla f(x_k),s\rangle
=\arg\min_{s\in P}\langle -\nabla f(x_k),s\rangle,
\]

that is `lmo.solver.solve(poly, c=-gradient, start=x_k)`. The standard step is
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
- `status`, why the run stopped (table below). Only `converged` makes a
  stationarity claim; **no status means "global optimum"**.

| `status` | Meaning | Returned point |
|---|---|---|
| `converged` | \(g \le\) `tol` | in \(P\), stationary up to `tol` |
| `max_iter` | iteration budget spent | in \(P\), gap at that point reported |
| `line_search_failed` | 12 halvings of the step never improved the objective | in \(P\), not stationary |
| `lp_not_optimal` | the oracle returned no optimum | in \(P\), gap \(+\infty\) after a move |
| `oracle_inconsistent` | the oracle said "optimal" but its vertex is outside \(P\) or worse than \(x_k\) | in \(P\) (the vertex is **not** used), gap \(+\infty\) |
| `stalled` | `stall_window` consecutive steps each gained \(<\) `stall_tol` (opt-in) | in \(P\), not stationary |

Every status returns a point of \(P\): the **geometric** validity never depends on the
status, the optimization claim always does. A caller that reports an "optimized" plan
must check `FrankWolfeResult.converged` (or `Trace.converged`), not merely that a plan
came back.

## Assumptions, and how each one is enforced

- \(x_0\in P\) (in practice: the L1 output of milestone 2). **Checked**: a start that
  violates \(P\) (budget box included) by more than `tolerances.FW_FEASIBILITY_M`
  (\(10^{-6}\) m) raises `InvariantViolation` naming the worst row, before any LP.
- The oracle is right. **Checked at every iteration**: a vertex \(s_k\) outside \(P\)
  (beyond `FW_FEASIBILITY_M`), or with a gap below \(-\)`FW_FEASIBILITY_M`
  \(\lVert\nabla f\rVert_1\) (worse than \(x_k\) itself, which no minimiser can be), is
  never stepped towards: the run stops on `oracle_inconsistent` at \(x_k\).
- Every iterate stays in \(P\). **Checked**: a step that leaves \(P\) (possible only with a
  faulty injected `StepStrategy`) raises `InvariantViolation`.
- \(P\) is the domain the final validator checks, or a subset of it. In
  `legalize`, \(P\) is the L1 polytope with contacts frozen, the budget box and the
  inner area chords: every point of it satisfies the original constraints
  (no overlap, outline, load-bearing sides, \(w h \ge a\)), and the decoded plan is
  re-checked by `certify.proof.verify_exactly` against the **original** nonlinear
  constraints, never against the linear approximation. The tangent cuts of
  [area cuts](area-cuts.md) (an outer approximation) are **not** used by Frank-Wolfe.
- Every call passes `start=x`: the GLOP model is reused (`ARCHITECTURE.md` §10).
- Iterates are convex combinations of vertices, hence in \(P\).
- A budget \(\Delta\) is the box \(\lVert x-\hat x\rVert_\infty\le\Delta\) around the
  **proposed** plan \(\hat x\), shared by the classic pass and Frank-Wolfe, so that it
  is spent once. Centring it on the L1 point \(x_0\) allowed up to \(2\Delta\) in total
  (measured: 0.55 m for \(\Delta = 0.3\) m). The box always contains \(x_0\), which
  meets the budget only up to the LP tolerance when the budget is saturated. The proof
  checks \(\max \lvert x - \hat x\rvert \le \Delta\); a budget too small for the plan
  raises `Infeasible`.
- After L1, `freeze_contacts` turns saturated separations into equalities and pins
  \(x, y\) to saturated outline edges: Frank-Wolfe keeps a tiling (no gap between rooms)
  while moving interior partitions. Saturated minimum widths stay free: a narrow room
  can grow.

## Displacement: penalty, metrics, and why the budget saturates

**Penalty.** `frank_wolfe(..., penalty=λ, reference=x̂)` maximises

\[
F(x) = f(x) - \tfrac{\lambda}{2}\lVert x - \hat x\rVert_2^2 ,
\]

whose gradient \(\nabla f(x) - \lambda (x - \hat x)\) is what the oracle receives. The
line search and the monotonicity are on \(F\); `value` still reports \(f\) and
`objective` reports \(F\), so a calibration of \(f\) stays valid. \(\lambda\) is in
indicator units per m²; \(\lambda = 0\) (default) is the plain surrogate.

**Budget box and its diagnosis.** `frank_wolfe(..., budget=Δ, reference=x̂)` intersects
\(P\) with \(\lVert x-\hat x\rVert_\infty \le Δ\) (always keeping \(x_0\)). The trace then
records `Trace.budget_active`, the columns on the box at the returned point, and
`Trace.active_bounds`, every tight bound and row. `Trace.displacements` gives
\(\lVert x_k-\hat x\rVert_\infty\) per iterate.

**Metrics.** `solve.displacement.measure_displacement(proposed, corrected)` measures,
room by room, the largest side shift (m), the signed and relative area change, and the
centre shift of every opening derived from its wall; `combined(wall=, area=,
opening=)` weights them explicitly (no canonical weights exist). `summarize(values)`
returns mean, median, 10–90 % interval, extremes and a histogram;
`count_saturated(values, budget=Δ)` counts the variants that reached Δ. Meeting a
budget is **not** preserving the design: these numbers describe geometry only.

**Why the budget saturates (milestone 9: 36 of 48 variants at exactly 3.00 m).**
This is the expected behaviour of the method, not a numerical artefact:

1. Without a penalty, nothing in \(f\) rewards staying close to \(\hat x\). Wherever
   \(f\) increases across the box, its maximiser over \(P \cap\) box is a vertex, and
   the oracle returns exactly such vertices. On the synthetic 5 × 3 grid
   (15 rooms, `AnalyticSurrogate`, azimuths 0/90/180/270°), every run with
   Δ ≤ 0.5 m converges in 2–3 iterations **on the box** (displacement = Δ).
2. For larger Δ the run stops before the box, but on `line_search_failed`, not on
   convergence: the analytic surrogate is only piecewise smooth, its gradient agrees
   with finite differences at \(h = 10^{-7}\) m but not at \(10^{-5}\) m, while the
   smallest trial step is \(2/(k+2)/2^{12}\) of a direction of several metres. The gain
   is then not monotone in Δ (azimuth 0°: +8.70 at Δ = 2 m, +8.31 at Δ = 3 m).
3. A penalty moves the optimum inside the box: on the same plan at azimuth 0°,
   Δ = 1 m, λ = 1 gives displacement 0.28 m for a gain of 1.18 (vs 1.00 m and 4.99
   without penalty); λ = 4 gives 0.07 m for 0.28.

So a saturated budget means "the surrogate would have moved further", and the
reported gain is a function of Δ. Report it as such: the gain **with** its
displacement, for several Δ and λ (`solve.sweep.sweep`), never a single gain at a
single budget.

## Iteration budgets

`solve.sweep.sweep(poly, surrogate, orientation, start, max_iters=..., budgets=...,
penalties=...)` reruns the same start over the grid and returns, per run, `status`,
`iterations`, surrogate `gain`, `gap`, `displacement`, `budget_bound` and wall-clock
`time_ms` (the only non-reproducible column). `success_rate(rows)` returns
`(converged, total)`, a pair to feed a Wilson interval, never a bare ratio. On the
synthetic grid above, 3 of 18 runs per azimuth converge, all of them budget-bound
with λ = 0; raising `max_iter` from 50 to 200 changes nothing, because the runs stop
on the line search first. The default `max_iter = 50` is therefore not the limiting
factor there; the smoothness of the surrogate is.

## Reproducibility

`Trace.parameters` records every setting as sorted `(name, text)` pairs: `max_iter`,
`tol`, `budget`, `reference`, `penalty`, `away_steps`, `strategy` (its `repr`),
`stall_window`, `stall_tol`, the step rule and `FW_FEASIBILITY_M`. With the iterates
\(x_k\), values, gaps, steps and away flags already in `Trace.iterations`, a run can be
replayed and audited without rerunning it. The solver is deterministic: two runs with
the same inputs give identical traces (only `lp_ms` differs).

## Derivation

Frank-Wolfe (1956): move towards a vertex, with a decreasing step. The away steps of
Lacoste-Julien & Jaggi (2015) remove mass from the worst active vertex, which speeds
up convergence on faces.

The iterate is kept as \(x=\sum_i w_i v_i\) over active vertices \(v_i\) (weights
\(w_i>0\), \(\sum_i w_i=1\)). With \(a=\arg\min_i\langle\nabla f(x),v_i\rangle\), the away
direction \(d_A=x-v_a\) is taken when \(\langle\nabla f,d_A\rangle>\langle\nabla
f,s-x\rangle\) and \(w_a<1\); its maximum step is \(\gamma_{\max}=w_a/(1-w_a)\), else
\(\gamma_{\max}=1\). The weight update is

- plain step: \(w\leftarrow(1-\gamma)w\), then \(w_s\mathrel{+}=\gamma\) (\(s\) added
  if new);
- away step: \(w\leftarrow(1+\gamma)w\), then \(w_a\mathrel{-}=\gamma\) (at
  \(\gamma_{\max}\), \(w_a=0\));

vertices whose weight falls to \(\le 10^{-12}\) are dropped and the rest renormalized.
The line search tries at most 12 halvings and reports `line_search_failed` otherwise.

The identity oracle = legalizer is the core of the project: one solver, two cost
vectors \(c\).

## Code

`frank_wolfe` → `FrankWolfeResult` (`x`, `value`, `objective`, `gap`, `status`,
`converged`, `iterations`, `trace`, `duals`). `Trace.parameters`,
`Trace.active_bounds`, `Trace.budget_active`, `Trace.displacements` and
`Trace.objectives` serve the diagnosis above. `Trace.iterates`, `Trace.values`, `Trace.status` and
`Trace.final_gap` serve the acceptance criteria (the French names `iteres`, `objectif`,
`ecarts` and the `Iteration` fields `valeur`, `pas` remain as deprecated aliases).

## Use

| Do | Do not |
|---|---|
| Plug in any `Surrogate` | Import `light.analytic` from `solve` |
| Report a gain with its displacement, `budget_active` and `status` | Report a gain at one budget as "the" gain, or a `line_search_failed` run as optimized |
| Read `gap` with `status` as a stationarity diagnostic | Read `gap` as a bound on the optimum (no shipped surrogate is concave), or confuse it with a coverage \(1-\alpha\) |

## Source

Frank & Wolfe (1956), *An algorithm for quadratic programming*, Naval Research
Logistics Quarterly. Lacoste-Julien & Jaggi (2015), *On the Global Linear Convergence
of Frank-Wolfe Optimization Variants*, NeurIPS. Lacoste-Julien (2016), *Convergence
Rate of Frank-Wolfe for Non-Convex Objectives*, arXiv:1607.00345.
[Bibliography](sources.md).
