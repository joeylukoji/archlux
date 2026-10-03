# Epigraph of the L1 distance

**Code:** `geom.polytope.extend_l1_slack`, `api.gradient_distance`.

## Statement

We want the valid plan *closest* to the proposed plan \(\hat x\in\mathbb{R}^n\),
in the sense

\[
\min_x \lVert x-\hat x\rVert_1 = \min_x \sum_{i=1}^n \lvert x_i-\hat x_i\rvert,
\]

with \(x\) in the [polytope](separated-polytope.md). The absolute value is not
linear. The **epigraph** (Bertsimas & Tsitsiklis, 1997, §1.3) introduces
\(e_i\ge 0\) such that

\[
e_i \ge x_i-\hat x_i, \qquad e_i \ge \hat x_i-x_i,
\]

equivalent, in the project's \(Ax\le b\) form, to

\[
x_i - e_i \le \hat x_i, \qquad -x_i - e_i \le -\hat x_i.
\]

The objective becomes linear:

\[
\min\; \sum_{i=1}^n e_i = \min\; c^\top (x,e),
\qquad
c=(0,\ldots,0,1,\ldots,1)\in\mathbb{R}^{2n}.
\]

The \(\hat x_i\) are in the **constraints**, never in \(c\).
`gradient_distance` reads only the dimension \(n\) of \(\hat x\).

## Assumptions

- Columns \(0..n-1\) unchanged (geometric variables); slacks in \(n..2n-1\),
  named `e.<variable>`.
- Both families of inequalities are **mandatory**. Omitting one leaves \(e_i\)
  free on one side: the apparent displacement blows up (`MILESTONE-2.md` §10).
- If \(\hat x\) is already admissible, the optimum is \(e=0\), \(x^\star=\hat x\).

## Derivation

For \(t\in\mathbb{R}\), \(\lvert t\rvert = \min\{ e : e\ge t,\; e\ge -t\}\).
Set \(t=x_i-\hat x_i\). Sum the \(e_i\) and stay in the enlarged polytope.

The bounds of the \(e_i\) are \((0,+\infty)\), translated into `solver.infinity()` for
GLOP (a Python `float('inf')` is not a GLOP bound).

## Use cases

| Do | Do not |
|---|---|
| Classic legalization (`objective is None`) | Put \(\hat x\) in \(c\) (the objective would stop being the sum of the slacks) |
| Cap each \(e_i\) with `budget=` | Believe that L1 *fills* the envelope: separations are inequalities, a plan with holes stays close to itself. [Gaps](exact-proof.md) are only guaranteed if the input is already a tiling (or an overlap whose union covers the outline) |
| Read `e.<name>` back in `index` | Vectorize a plan with the *extended* index (the `e.*` keys are not rooms) |

## Source

Bertsimas & Tsitsiklis (1997), §1.3 — LP formulation of absolute values.
[Bibliography](sources.md).
