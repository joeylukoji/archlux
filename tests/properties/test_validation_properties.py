"""Properties of the independent validator (``certify.validation``).

Three promises:

- an accepted plan satisfies every hard constraint: whatever ``legalize`` returns, with
  or without a surrogate, ``validate_plan`` re-checks it from its coordinates alone;
- a wrong surrogate cannot make an invalid plan pass: the surrogate only steers the
  optimizer, and the validator never reads it, nor the certificate the plan carries;
- the validator is never more lenient than the exact proof, nor than the independent
  checker of ``tests/checkers.py``.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.certify.proof import verify_exactly
from archlux.certify.validation import validate_plan
from archlux.errors import ArchluxError
from archlux.light.analytic import AnalyticSurrogate
from archlux.types import Certificate, Context, GeometricProof, PerformanceBound, Plan
from tests import checkers
from tests.properties.strategies import (
    DEFAULT_CONTEXT,
    GATE_EXAMPLES,
    arbitrary_plans,
    realistic_scenarios,
    valid_plans,
)

_SETTINGS = settings(
    max_examples=GATE_EXAMPLES, deadline=None, derandomize=True, report_multiple_bugs=False
)


class _Adversarial(AnalyticSurrogate):
    """A surrogate whose gradient is large and meaningless: the worst steering."""

    def gradient(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
        del orientation, glazing
        return 1e6 * np.sign(np.sin(np.arange(len(x), dtype=float) + 1.0))


class _Negated(AnalyticSurrogate):
    """A surrogate pointing the wrong way everywhere."""

    def gradient(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
        return -super().gradient(x, orientation, glazing=glazing)


def _forged(plan: Plan) -> Plan:
    """The plan wearing a certificate that claims everything holds."""
    proof = GeometricProof(
        valid=True,
        overlap=False,
        gaps=False,
        areas_ok=True,
        structure_kept=True,
        max_displacement=0.0,
    )
    bound = PerformanceBound(
        indicator="sDA",
        value=1.0,
        lower=1.0,
        upper=1.0,
        coverage=0.99,
        n_calibration=10_000,
        regime="exchangeable",
    )
    return replace(plan, certificate=Certificate(geometry=proof, performance=bound))


@settings(max_examples=200, deadline=None)
@given(plan=valid_plans())
def test_a_valid_tiling_is_valid_with_exact_evidence(plan: Plan) -> None:
    report = validate_plan(plan, DEFAULT_CONTEXT)
    assert report.valid, report.summary()
    assert report.evidence == "exact"


@_SETTINGS
@given(
    scenario=realistic_scenarios(),
    budget=st.none() | st.floats(min_value=0.05, max_value=1.0),
    objective=st.sampled_from([None, AnalyticSurrogate(), _Negated(), _Adversarial()]),
)
def test_an_accepted_plan_satisfies_every_hard_constraint(
    scenario: tuple[Plan, Context], budget: float | None, objective: object
) -> None:
    """Whatever steered the optimizer, an accepted plan passes the independent validator."""
    plan, ctx = scenario
    try:
        result = archlux.legalize(plan, ctx, objective=objective, budget=budget)  # type: ignore[arg-type]
    except ArchluxError:
        return  # a typed refusal is allowed; an invalid accepted plan is not
    report = validate_plan(result, ctx, reference=plan, budget=budget)
    assert report.valid, report.summary()
    assert report.matches(result)


@_SETTINGS
@given(plan=arbitrary_plans())
def test_a_forged_certificate_never_makes_a_plan_valid(plan: Plan) -> None:
    """The validator ignores the certificate: forging one changes nothing."""
    ctx = replace(DEFAULT_CONTEXT, outline=plan.outline)
    honest = validate_plan(replace(plan, certificate=None), ctx)
    assert validate_plan(_forged(plan), ctx).results == honest.results


@_SETTINGS
@given(plan=arbitrary_plans())
def test_never_more_lenient_than_the_exact_proof(plan: Plan) -> None:
    ctx = replace(DEFAULT_CONTEXT, outline=plan.outline)
    if validate_plan(plan, ctx).valid:
        assert verify_exactly(plan, ctx).valid
        assert checkers.violations(plan, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios(), shift=st.floats(min_value=1e-4, max_value=0.5))
def test_a_shifted_room_is_refused(scenario: tuple[Plan, Context], shift: float) -> None:
    """Moving one room of a valid tiling opens a gap or an overlap: always refused.

    Rooms are at least 1 m wide, so a shift of 1e-4 m opens at least 1e-4 m2, a hundred
    times the gap tolerance; below ``GAP_M2`` the shift is within the declared tolerance.
    """
    plan, ctx = scenario
    first, *rest = plan.rooms
    moved = replace(plan, rooms=(replace(first, x=first.x + shift), *rest))
    assert not validate_plan(moved, ctx).valid
