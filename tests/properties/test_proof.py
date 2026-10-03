"""Properties of the exact check: `MILESTONE-2.md` §6.

The guillotine tilings of :func:`valid_plans` are exact by construction (integer
centimetres), without filtering by ``verify_exactly``: the test is not tautological.
"""

from __future__ import annotations

from hypothesis import given, settings

from archlux.certify.proof import verify_exactly
from archlux.types import Plan
from tests.properties.strategies import DEFAULT_CONTEXT, valid_plans


@given(plan=valid_plans())
@settings(max_examples=200, deadline=None)
def test_a_valid_plan_passes(plan: Plan) -> None:
    proof = verify_exactly(plan, DEFAULT_CONTEXT)
    assert proof.valid
    assert proof.overlap is False
    assert proof.gaps is False
    assert proof.areas_ok
    assert proof.structure_kept
