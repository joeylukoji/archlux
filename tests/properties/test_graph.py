"""Properties of the constraint graph: `MILESTONE-2.md` §2.

The two properties that matter: no pair can escape separation, and the transitive
reduction loses no order information.
"""

from __future__ import annotations

import itertools

from hypothesis import given, settings

from archlux.geom.graph import (
    RelativeOrder,
    build_graph,
    deduce_order,
    transitive_reduction,
)
from archlux.types import Plan
from tests.properties.strategies import arbitrary_plans, valid_orders


@given(plan=arbitrary_plans())
@settings(max_examples=200, deadline=None)
def test_every_plan_gives_an_acceptable_order(plan: Plan) -> None:
    """**The assembly contract of the pipeline.**

    ``deduce_order`` and ``build_graph`` can each be correct alone while the chain stays
    unusable. This property says that the second always accepts what the first produces,
    including on absurd plans, which are the real input of the system.
    """
    order = deduce_order(plan)
    build_graph(order, list(order.rooms))


@given(order=valid_orders())
@settings(max_examples=200, deadline=None)
def test_every_pair_is_separated(order: RelativeOrder) -> None:
    """Without separation on at least one axis, overlap stays possible."""
    graph = build_graph(order, list(order.rooms))
    for a, b in itertools.combinations(order.rooms, 2):
        assert graph.has_separation(a, b)


@given(order=valid_orders())
@settings(max_examples=200, deadline=None)
def test_reduction_preserves_the_closure(order: RelativeOrder) -> None:
    """The reduction removes edges, never information.

    That is what makes reducing safe: the removed constraints stay implied by those that
    remain.
    """
    full = build_graph(order, list(order.rooms))
    reduced = transitive_reduction(full)
    assert full.closure() == reduced.closure()


@given(order=valid_orders())
@settings(max_examples=100, deadline=None)
def test_the_reduction_never_grows(order: RelativeOrder) -> None:
    """The number of edges can only decrease: that is the point of the step."""
    full = build_graph(order, list(order.rooms))
    reduced = transitive_reduction(full)
    for axis in ("horizontal", "vertical"):
        assert getattr(reduced, axis).number_of_edges() <= getattr(full, axis).number_of_edges()
