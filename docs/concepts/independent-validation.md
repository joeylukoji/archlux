# Independent validation

The solver says a plan is admissible; that is not enough. Before `legalize` returns a
plan, a **second, independent check** re-reads it from its coordinates alone (no LP
status, no polytope, no Frank-Wolfe trace) and re-checks every explicit rule. A plan is
returned only if every **hard** rule holds again; otherwise `legalize` raises
`InvariantViolation`. A solver bug cannot certify itself.

## What is checked

Every rule has an identifier, a kind, a tolerance and a method. Each result is
`satisfied`, `violated` or `unknown`, with the worst measured value and a reason. A
check that cannot run is `unknown`, **never** `satisfied`, and an `unknown` hard rule
refuses the plan like a violated one.

| Kind | Rules |
|---|---|
| **Hard** (never violated by a returned plan) | `rooms.finite`, `rooms.non_degenerate`, `ids.unique`, `rooms.no_overlap`, `outline.covered`, `outline.contains_rooms`, `rooms.min_area` (a fused room as a whole), `rooms.min_width`, `structure.not_crossed`, `structure.not_moved`, `walls.non_degenerate`, `openings.on_known_wall`, `openings.within_wall`, `openings.disjoint`, `openings.sill_below_head`, `displacement.budget` (when a budget is given) |
| **Soft** (reported, never blocking) | `rooms.connected` |

Constraints added during optimization (a cut, a frozen contact) can be passed to
`archlux.certify.validate_plan(..., extra=...)` and are checked with the same schema.

## Exact or numeric: the evidence

A validation is not always a proof. The report says which:

| Evidence | Meaning | Report banner |
|---|---|---|
| `exact` | every hard rule was settled in **exact rational arithmetic** (the stored floats read as fractions) against a declared tolerance | `[EXACT]` |
| `numeric` | at least one hard rule relied on a **floating-point** computation (GEOS) with tolerance — typically a non-rectangular outline or a fused room | `[NUMERIC]` |
| `refused` | a hard rule is violated or unknown: no plan is returned | — |

The tolerance is part of the claim: "no overlap" means "no overlap larger than
\(10^{-9}\ \text{m}^2\)", and the report prints the tolerance next to each measure.

## What it never establishes

Whatever the verdict, the validation is about the explicit geometric model above and
nothing else. It does **not** establish building-code compliance, accessibility, fire
safety, structural soundness, constructibility or daylight performance. The summary
carries this list (`scope`) so that no reader has to guess.

## Reading it from a certificate

```python
import archlux

plan = archlux.Plan(
    rooms=(
        archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=5.0, h=9.0),
        archlux.Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=9.0),
    ),
    outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
)
ctx = archlux.Context(
    structure=archlux.Structure(load_bearing_walls=()),
    orientation=archlux.Orientation(deg=180.0),
    regulation=archlux.Regulation(min_areas=(), min_width=1.0),
)
fixed = archlux.legalize(plan, ctx)
summary = fixed.certificate.validation
assert summary.valid and summary.evidence == "exact"
assert "rooms.no_overlap" in summary.checked
assert "fire safety" in summary.scope

# The full report, one measure per rule, recomputed on demand:
from archlux.certify import validate_plan

print(validate_plan(fixed, ctx).summary())
```

The summary is bound to the plan it checked by a fingerprint of its geometry
(`summary.plan_fingerprint`); `validate_plan(...).matches(plan)` confirms that a report
is about the final plan and not an intermediate state.

## How the optimizer stopped

With an objective, the certificate also records how Frank-Wolfe stopped
(`certificate.optimization`: status, iterations, gap). Every status returns a plan of
the admissible domain, so the geometry above holds regardless; but only `converged`
means the run reached its stationarity tolerance. Any other status (`max_iter`,
`stalled`, `line_search_failed`, `untrusted_gradient` when a guarded surrogate refused
its gradient…) is printed as "geometrically valid, NOT an optimised plan". No status
means "global optimum": no shipped surrogate is concave.
