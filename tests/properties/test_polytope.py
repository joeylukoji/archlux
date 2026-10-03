"""Properties of the polytope: `MILESTONE-2.md` §3.

The property that matters: **a valid plan belongs to its own polytope**. If it fails,
the model does not describe the set it claims to describe, and everything downstream
(solver, certificate) reasons on the wrong domain.
"""

from __future__ import annotations

from hypothesis import given, settings

from archlux.geom.graph import RelativeOrder, deduce_order
from archlux.geom.polytope import build_polytope, vectorize
from archlux.types import Context, Plan
from tests.properties.strategies import (
    DEFAULT_CONTEXT,
    contexts,
    valid_orders,
    valid_plans,
)


@given(order=valid_orders(), ctx=contexts())
@settings(max_examples=200, deadline=None)
def test_consistent_dimensions(order: RelativeOrder, ctx: Context) -> None:
    """One origin per row, one column per variable."""
    poly = build_polytope(order, ctx)
    assert poly.A.shape[0] == len(poly.origins)
    assert poly.A.shape[1] == len(poly.index)
    assert poly.b.shape[0] == poly.A.shape[0]
    assert len(poly.bounds) == len(poly.index)


@given(plan=valid_plans())
@settings(max_examples=200, deadline=None)
def test_a_valid_plan_is_in_the_polytope(plan: Plan) -> None:
    """The central contract of the model.

    An exact tiling of the outline necessarily satisfies the order deduced from it;
    otherwise ``legalize`` would move walls on a plan that had no defect.
    """
    poly = build_polytope(deduce_order(plan), DEFAULT_CONTEXT)
    assert poly.contains(vectorize(plan, poly.index), tol=1e-9)


@given(plan=valid_plans())
@settings(max_examples=100, deadline=None)
def test_legalizing_a_valid_plan_is_idempotent_in_domain(plan: Plan) -> None:
    """The point stays in the polytope after a vectorization round trip."""
    from archlux.geom.polytope import devectorize

    poly = build_polytope(deduce_order(plan), DEFAULT_CONTEXT)
    point = vectorize(plan, poly.index)
    assert devectorize(point, plan, poly.index) == plan
