# Simplex, duals and Farkas

**Code:** `lmo.solver.solve`, `_certificat_farkas`, `_is_feasible`.

## Statement — primal

\[
\min_x \; c^\top x
\quad\text{s.t.}\quad
Ax \le b,\quad
A_{\mathrm{eq}} x = b_{\mathrm{eq}},\quad
\ell \le x \le u,
\]

plus the [cuts](area-cuts.md) \(\sum_j \alpha_j x_j \ge \beta\).

**This module does not know where \(c\) comes from.** L1 distance or \(-\nabla\) of daylight:
same oracle (`ARCHITECTURE.md` §2).

Backend: OR-Tools **GLOP** (simplex).

## Duals

With `duals=True`, the prices are extracted **in the order of the rows of \(A\)** — the
only order that can be matched with `Polytope.origins`. Cuts and equalities are
not in this vector at milestone 2: the dual of an area cut is not labelled
yet. Components with \(\lvert y_i\rvert \le 10^{-9}\) are omitted at the API.

A dual price reads: "relaxing this constraint by one metre changes the objective by
\(y_i\)". This is standard LP duality (Bertsimas & Tsitsiklis, ch. 4).

## Infeasible vs unbounded

GLOP returns the `INFEASIBLE` code for an **unbounded** problem too. Discriminant:
the LP with a zero objective on the same system. An LP with a zero objective cannot be
unbounded; if it finds a point, the failure came from \(c\), not from the program.

## Derivation — Farkas certificate (phase I)

Farkas' lemma (Schrijver, 1986, §7.3; Bertsimas & Tsitsiklis, ch. 4): the
system \(Ax\le b\) is infeasible if and only if there exists \(y\ge 0\) such that

\[
A^\top y = 0 \quad\text{and}\quad b^\top y < 0
\]

(theorem of the alternative for inequalities; equalities and bounds reduce
to this case). Such a \(y\) *designates* the conflicting constraints.

**What the code computes.** Auxiliary problem (phase I): relax each
inequality \(a_i x \le b_i\) by \(s_i\ge 0\),

\[
\min\; \sum_i s_i
\quad\text{s.t.}\quad
a_i x - s_i \le b_i.
\]

Always feasible. If the optimum is strictly positive, the primal is not.
The duals of the relaxed constraints, **negated** (OR-Tools returns the sign opposite to
the \(y\ge 0\) convention for a \(\le\) row), are the returned certificate.
The \(\ge\) cuts are relaxed in the other direction; without that, an impossible
cut makes the auxiliary problem itself infeasible, and its duals no longer mean
anything.

The vector has one entry per row of \(A\). Crossed with `origins`, it becomes a
domain label: `separation horizontale a|b`, `contour droit b`.

## Equalities and exact verification (batch 1.5c)

**Equalities are relaxed too.** The auxiliary problem relaxes each row of \(A_{eq}\)
(tiling, fusions, frozen contacts) with two slacks. Before, a conflict among those
equalities left it without an optimum and the certificate empty: 68 of 200 noisy
benchmark plans were refused with `origines non renseignees`. Each equality now carries
a label (`Polytope.origins_eq`), and the refusal names every row with a non-zero weight.

**The certificate is checked, not believed.** Let \(y \ge 0\) be the multipliers of
\(Ax \le b\) and \(z\) those of \(A_{eq}x = b_{eq}\). Every admissible \(x\) satisfies

\[
r^\top x \le \beta, \qquad r = A^\top y + A_{eq}^\top z, \qquad
\beta = b^\top y + b_{eq}^\top z .
\]

With bounds \(l \le x \le u\),
\(\min_{l \le x \le u} r^\top x = \sum_j \min(r_j l_j, r_j u_j)\). If this minimum exceeds
\(\beta\), no admissible \(x\) exists. `certify.farkas.verify_infeasibility` computes it
in exact rational arithmetic (a float multiplier is an exact rational), so a verified
certificate is a proof even if the solver rounded; a noisy one can fail to verify, never
verify a feasible system. On the noisy benchmark, 88 of 89 certificates verify.

**Scope.** The certificate proves that the polytope of **this relative order** is empty.
Another order might admit a valid plan: `Infeasible` and `is_feasible` say so.

**Tightened domains.** The area cutting loop tightens variable bounds, which is not an
outer approximation; an infeasible verdict on a tightened domain said nothing about the
real problem (8 occurrences on the benchmark). The loop now solves the original domain
before concluding.

## Use cases

| Do | Do not |
|---|---|
| `start=` to reuse the model (same polytope, new objective) | Reuse the cache if *cuts* were added — the system has changed |
| Read `Infeasible.origins`, not only the message | Translate a dual as "row 47" |
| Distinguish `infaisable` / `non_borne` / `limite` | Merge them into one "not optimal" boolean |

## Source

- Bertsimas & Tsitsiklis (1997), ch. 4 — duality and Farkas.
- Schrijver (1986), §7.3 — Farkas' lemma.
- Kelley (1960) — cuts invalidate the basis, hence the cache refusal.

[Bibliography](sources.md).
