"""Acceptance criterion of milestone 2. The milestone is done when this test passes.

One test, one property: *every* output of ``legalize`` is geometrically valid. The
guillotine tilings of :func:`valid_plans` are the domain where a valid plan always
exists inside the envelope; 500 examples, deadline lifted.
"""

from __future__ import annotations

from hypothesis import given, settings

import archlux
from archlux.types import Plan
from tests.properties.strategies import DEFAULT_CONTEXT, valid_plans


@given(plan=valid_plans())
@settings(max_examples=500, deadline=None)
def test_every_output_is_valid(plan: Plan) -> None:
    """`MILESTONE-2.md` §0: the single acceptance criterion of the milestone."""
    result = archlux.legalize(plan, DEFAULT_CONTEXT)
    assert result.certificate is not None
    assert result.certificate.geometry.valid
    assert result.certificate.performance is None
