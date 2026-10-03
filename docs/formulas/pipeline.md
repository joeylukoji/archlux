# Pipeline of the classic legalization

**Code:** `api.legalize` (`objective is None`).

## Statement

\[
\min_{x,e}\; \sum_i e_i
\quad\text{s.t.}\quad
x\in P,\;
e\ge \lvert x-\hat x\rvert,\;
(w_p,h_p)\in K_p,
\]

where \(P\) is the [order polytope](separated-polytope.md), \(K_p\) the
[area superlevel set](area-cuts.md) of room \(p\), and \(\hat x\) the
[vectorized](l1-epigraph.md) proposed plan.

Then: devectorize, [verify exactly](exact-proof.md), attach the
`Certificate`. If the proof fails → `InvariantViolation` (internal bug, never
silent). If the LP is infeasible → `Infeasible` with
[Farkas](farkas.md).

## Chain, one line per step

1. `deduce_order` — the generator decides the order ([graph](relative-order.md)).
2. `build_polytope` — \(Ax\le b\).
3. `extend_l1_slack` — \((x,e)\in\mathbb{R}^{2n}\).
4. `gradient_distance` — \(c=(0_n,1_n)\).
5. `solve_with_areas` — GLOP + Kelley + bounds.
6. `devectorize` — walls and glazing follow (glazing relative to its wall).
7. `verify_exactly(..., reference=plan)` — \(\delta_\infty\).
8. `Certificate(geometry=..., performance=None, duals=...)`.

`performance is None`: in classic mode there is **nothing probabilistic** to
claim.

## Performance branch (`objective=Surrogate`)

After step 8, the L1 point becomes \(x_0\). Saturated contacts become
equalities (`freeze_contacts`): Frank-Wolfe stays a tiling. Then the minimum areas
are replaced by an **inner** polyhedral approximation
(`inner_area_constraints`, see [area cuts](area-cuts.md)): every point of
the domain, hence every iterate, keeps every minimum area, and no tangent cut is needed.
Then [Frank-Wolfe](frank-wolfe.md) maximizes the surrogate, **same LP oracle**,
`start=x` at every round. The output is verified exactly again; an invalid
iterate raises `InvariantViolation` — no silent fallback to L1.
With `legalize(..., calibration=...)`, the surrogate's prediction at the returned
plan is bounded by `certify.bound.bound_selected_plan`, in the **selected** regime:
the optimizer chose the plan, so the nominal coverage is not guaranteed and the report
says so. The calibration is checked before any solving. Without calibration,
`performance is None` and the report writes `NOT EVALUABLE`.

## Use cases

| Do | Do not |
|---|---|
| `legalize(plan, ctx)` on an almost valid tiling | Expect 100 % success on `plans_quelconques` × a small envelope: the room program may not fit → `Infeasible` |
| Read `q.certificate.geometry.valid` | Aggregate proof and prediction into one score |
| Import only `light.protocol.Surrogate` | Import `bench` from `api` (forbidden by `tests/test_dependances.py`) |

Budget of `ARCHITECTURE.md` §9: \(< 20\,\mathrm{ms}\) for 15 rooms.

## Source

Composition of the pages of this folder; not a separate theorem.
