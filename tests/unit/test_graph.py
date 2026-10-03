"""Separation constraint graph: deterministic cases.

`MILESTONE-2.md` §2. The founding rule: for every pair of rooms, **at least one**
separation must exist. Without it, overlap stays possible and no later constraint
catches it.
"""

from __future__ import annotations

import pytest

from archlux.errors import InconsistentOrder, MissingSeparation
from archlux.geom.graph import (
    RelativeOrder,
    build_graph,
    deduce_order,
    transitive_reduction,
)
from archlux.types import Plan, Room


def _plan(*rooms: Room) -> Plan:
    return Plan(rooms=rooms, walls=(), openings=(), outline=())


def _square(name: str, x: float, y: float, side: float = 1.0) -> Room:
    return Room(id=name, type="living_room", x=x, y=y, w=side, h=side)


class TestBuildGraph:
    """Assembly and validation of the order."""

    def test_simple_separation(self) -> None:
        """A declared horizontal edge ends up in the horizontal graph."""
        order = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B"))
        graph = build_graph(order, ["A", "B"])
        assert ("A", "B") in graph.horizontal.edges

    def test_cycle_detected(self) -> None:
        """The order "A left of B left of A" has no geometric solution."""
        order = RelativeOrder(horizontal=(("A", "B"), ("B", "A")), vertical=(), rooms=("A", "B"))
        with pytest.raises(InconsistentOrder) as capture:
            build_graph(order, ["A", "B"])
        assert capture.value.axis == "horizontal"
        assert set(capture.value.cycle) == {"A", "B"}

    def test_vertical_cycle_detected(self) -> None:
        """The same defect on the vertical axis is reported with the right axis."""
        order = RelativeOrder(horizontal=(), vertical=(("A", "B"), ("B", "A")), rooms=("A", "B"))
        with pytest.raises(InconsistentOrder) as capture:
            build_graph(order, ["A", "B"])
        assert capture.value.axis == "vertical"

    def test_unseparated_pair_refused(self) -> None:
        """Two rooms without separation can overlap: that is an input error."""
        order = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B", "C"))
        with pytest.raises(MissingSeparation) as capture:
            build_graph(order, ["A", "B", "C"])
        assert "C" in capture.value.pair

    def test_an_unknown_room_is_refused(self) -> None:
        """An edge towards a room missing from the declared set is inconsistent."""
        order = RelativeOrder(horizontal=(("A", "Z"),), vertical=(), rooms=("A", "B"))
        with pytest.raises(InconsistentOrder):
            build_graph(order, ["A", "B"])


class TestDeduceOrder:
    """Extraction of the relative order from a proposed plan."""

    def test_two_rooms_side_by_side(self) -> None:
        """Centers apart in x: the separation is horizontal."""
        order = deduce_order(_plan(_square("A", 0.0, 0.0), _square("B", 5.0, 0.0)))
        assert order.horizontal == (("A", "B"),)
        assert order.vertical == ()

    def test_two_stacked_rooms(self) -> None:
        """Centers apart in y: the separation is vertical."""
        order = deduce_order(_plan(_square("A", 0.0, 0.0), _square("B", 0.0, 5.0)))
        assert order.vertical == (("A", "B"),)
        assert order.horizontal == ()

    def test_the_really_separating_axis_wins(self) -> None:
        """**Regression.** Disjoint in x, overlapping in y: the separation is in x.

        Counter-example found by the polytope property test. ``A`` spans ``y ∈ [0, 1]``
        and ``B`` ``y ∈ [0, 9]``: they overlap vertically. But the distance between their
        centers is larger in y, so a rule based on the dominant axis produced
        ``y_A + h_A ≤ y_B``, i.e. ``1 ≤ 0``: a constraint that the original plan, valid
        as it was, violated.
        """
        order = deduce_order(
            _plan(
                Room(id="A", type="living_room", x=0.0, y=0.0, w=1.0, h=1.0),
                Room(id="B", type="living_room", x=1.0, y=0.0, w=1.0, h=9.0),
            )
        )
        assert order.horizontal == (("A", "B"),)
        assert order.vertical == ()

    def test_the_dominant_axis_settles_overlaps(self) -> None:
        """When the rooms overlap on both axes, the distance between centers decides.

        It is the only case where the heuristic applies, and it is precisely the defect
        that ``legalize`` exists to fix.
        """
        order = deduce_order(
            _plan(
                Room(id="A", type="living_room", x=0.0, y=0.0, w=4.0, h=4.0),
                Room(id="B", type="living_room", x=1.0, y=3.0, w=4.0, h=4.0),
            )
        )
        assert order.vertical == (("A", "B"),)
        assert order.horizontal == ()

    def test_two_adjoining_rooms_stay_separated(self) -> None:
        """**Floating-point regression.** ``1.0 + 3.47`` is ``4.470000000000001``.

        Two rooms that touch exactly end up overlapping by 1e-16 in binary. Without a
        contact tolerance, they fell into the degraded case and received a vertical
        constraint that the plan violated. The case arises as soon as a wall separates
        two adjacent rooms, that is, everywhere.
        """
        left = Room(id="A", type="living_room", x=1.0, y=0.0, w=3.47, h=9.0)
        right = Room(id="B", type="living_room", x=4.47, y=0.0, w=1.0, h=1.0)
        assert left.x + left.w != right.x  # the trap, in one line
        order = deduce_order(_plan(left, right))
        assert order.horizontal == (("A", "B"),)

    def test_is_deterministic(self) -> None:
        """Two readings of the same plan give the same order, at the same indices.

        A non-deterministic order would produce polytopes whose rows change from one run
        to the next, hence dual prices that cannot be compared.
        """
        plan = _plan(_square("c", 4.0, 0.0), _square("a", 0.0, 0.0), _square("b", 2.0, 3.0))
        assert deduce_order(plan) == deduce_order(plan)

    def test_the_deduced_order_is_accepted(self) -> None:
        """An order deduced from a real plan passes validation without an exception.

        It is the assembly contract between the two functions: without it, each can be
        correct alone while the chain stays unusable.
        """
        plan = _plan(
            _square("living_room", 0.0, 0.0, 4.0),
            _square("kitchen", 5.0, 0.0, 3.0),
            _square("bathroom", 0.0, 5.0, 2.0),
        )
        graph = build_graph(deduce_order(plan), list(plan.room_ids))
        assert graph.has_separation("living_room", "kitchen")
        assert graph.has_separation("living_room", "bathroom")


class TestTransitiveReduction:
    """Removal of the edges implied by transitivity."""

    def test_removes_the_redundant_edge(self) -> None:
        """``A→B→C`` makes ``A→C`` superfluous.

        The gain is not cosmetic: 15 rooms go from ~210 constraints to ~30, and the
        solver is called 50 times per performance legalization.
        """
        order = RelativeOrder(
            horizontal=(("A", "B"), ("B", "C"), ("A", "C")),
            vertical=(),
            rooms=("A", "B", "C"),
        )
        reduced = transitive_reduction(build_graph(order, ["A", "B", "C"]))
        assert ("A", "C") not in reduced.horizontal.edges
        assert ("A", "B") in reduced.horizontal.edges
        assert ("B", "C") in reduced.horizontal.edges

    def test_keeps_every_room(self) -> None:
        """Reducing the edges must never make a room disappear."""
        order = RelativeOrder(
            horizontal=(("A", "B"), ("B", "C"), ("A", "C")),
            vertical=(),
            rooms=("A", "B", "C"),
        )
        reduced = transitive_reduction(build_graph(order, ["A", "B", "C"]))
        assert set(reduced.horizontal.nodes) == {"A", "B", "C"}
