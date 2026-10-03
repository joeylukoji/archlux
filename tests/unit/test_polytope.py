"""Polytope assembly: `MILESTONE-2.md` §3, deterministic cases.

The expected rows are written by hand: `x_A + w_A − x_B ≤ 0` for "A left of B".
Comparing with a computation redone like the code would be tautological.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy import sparse

from archlux.errors import InvariantViolation
from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import (
    build_polytope,
    devectorize,
    freeze_contacts,
    vectorize,
)
from archlux.types import (
    Context,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
)

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(("bathroom", 5.0),), min_width=1.5),
)

ORDER_AB = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B"))

PLAN_AB = Plan(
    rooms=(
        Room(id="A", type="living_room", x=0.0, y=0.0, w=4.0, h=8.0),
        Room(id="B", type="bathroom", x=4.0, y=0.0, w=6.0, h=8.0),
    ),
    walls=(),
    openings=(),
    outline=CTX.outline,
)


class TestVariables:
    """Four variables per room, indexed deterministically."""

    def test_four_variables_per_room(self) -> None:
        """``x``, ``y``, ``w``, ``h``, and nothing else."""
        poly = build_polytope(ORDER_AB, CTX)
        assert len(poly.index) == 8
        assert set(poly.index) == {
            f"{room}.{field}" for room in ("A", "B") for field in ("x", "y", "w", "h")
        }

    def test_the_columns_are_contiguous(self) -> None:
        """The indices cover ``0..4n-1`` without a hole: that is what ``lmo`` assumes."""
        poly = build_polytope(ORDER_AB, CTX)
        assert sorted(poly.index.values()) == list(range(8))


class TestConstraints:
    """The content of the rows, not only their number."""

    def test_horizontal_separation_row(self) -> None:
        """The relation "A left of B" is written ``x_A + w_A − x_B ≤ 0``."""
        poly = build_polytope(ORDER_AB, CTX)
        row = next(i for i, o in enumerate(poly.origins) if o.startswith("separation horizontale"))
        expected = np.zeros(8)
        expected[poly.index["A.x"]] = 1.0
        expected[poly.index["A.w"]] = 1.0
        expected[poly.index["B.x"]] = -1.0
        assert np.allclose(poly.A.toarray()[row], expected)
        assert poly.b[row] == 0.0

    def test_outline_row(self) -> None:
        """``x_i + w_i ≤ W`` bounds the room inside the envelope."""
        poly = build_polytope(ORDER_AB, CTX)
        row = poly.origins.index("contour droit A")
        expected = np.zeros(8)
        expected[poly.index["A.x"]] = 1.0
        expected[poly.index["A.w"]] = 1.0
        assert np.allclose(poly.A.toarray()[row], expected)
        assert poly.b[row] == pytest.approx(10.0)

    def test_the_minimum_widths_are_in_the_bounds(self) -> None:
        """`MILESTONE-2.md` §3: ``w_i ≥ ℓ_min`` goes through ``bounds``, not through ``A``."""
        poly = build_polytope(ORDER_AB, CTX)
        assert poly.bounds[poly.index["A.w"]] == (1.5, 10.0)
        assert poly.bounds[poly.index["A.h"]] == (1.5, 8.0)
        assert poly.bounds[poly.index["A.x"]] == (0.0, 10.0)

    def test_no_area_constraint(self) -> None:
        """``w·h ≥ a`` is non-linear: deferred to the cuts of step 4."""
        poly = build_polytope(ORDER_AB, CTX)
        assert not any("surface" in o for o in poly.origins)


class TestOrigins:
    """`origins` is mandatory from the first version."""

    def test_one_origin_per_row(self) -> None:
        """Without this mapping, a dual price is "the number of row 47"."""
        poly = build_polytope(ORDER_AB, CTX)
        assert poly.A.shape[0] == len(poly.origins)

    def test_the_origins_are_readable(self) -> None:
        """A label must read in a project review, not only while debugging."""
        poly = build_polytope(ORDER_AB, CTX)
        assert all(isinstance(o, str) and len(o) > 3 for o in poly.origins)
        assert "separation horizontale A|B" in poly.origins


class TestContains:
    """Membership check, naive and independent of any solver."""

    def test_a_compliant_plan_is_inside(self) -> None:
        """The reference plan satisfies every row."""
        poly = build_polytope(ORDER_AB, CTX)
        assert poly.contains(vectorize(PLAN_AB, poly.index))

    def test_an_overlap_is_outside(self) -> None:
        """Moving B back two metres violates the separation."""
        poly = build_polytope(ORDER_AB, CTX)
        point = vectorize(PLAN_AB, poly.index)
        point[poly.index["B.x"]] = 2.0
        assert not poly.contains(point)

    def test_overflowing_the_outline_is_outside(self) -> None:
        """Widening B beyond the envelope violates the outline row."""
        poly = build_polytope(ORDER_AB, CTX)
        point = vectorize(PLAN_AB, poly.index)
        point[poly.index["B.w"]] = 20.0
        assert not poly.contains(point)

    def test_a_room_too_narrow_is_outside(self) -> None:
        """The minimum width is a bound, it counts too."""
        poly = build_polytope(ORDER_AB, CTX)
        point = vectorize(PLAN_AB, poly.index)
        point[poly.index["A.w"]] = 0.1
        assert not poly.contains(point)


class TestVectorization:
    """Round trip between plan and decision vector."""

    def test_round_trip(self) -> None:
        """``devectorize(vectorize(p))`` returns the original plan."""
        poly = build_polytope(ORDER_AB, CTX)
        point = vectorize(PLAN_AB, poly.index)
        assert devectorize(point, PLAN_AB, poly.index) == PLAN_AB

    def test_the_openings_follow_without_touch_up(self) -> None:
        """**The reason for the invariant of §6.**

        The vector carries only the rooms. Openings being relative to their wall, they
        go through devectorization intact: no resynchronization to write.
        """
        poly = build_polytope(ORDER_AB, CTX)
        point = vectorize(PLAN_AB, poly.index)
        point[poly.index["A.w"]] = 3.0
        result = devectorize(point, PLAN_AB, poly.index)
        assert result.openings == PLAN_AB.openings
        assert result.walls == PLAN_AB.walls

    def test_a_missing_room_is_reported(self) -> None:
        """Vectorizing a plan that lacks the rooms of the order is an internal bug."""
        poly = build_polytope(ORDER_AB, CTX)
        other = Plan(
            rooms=(Room(id="Z", type="living_room", x=0.0, y=0.0, w=1.0, h=1.0),),
            walls=(),
            openings=(),
            outline=CTX.outline,
        )
        with pytest.raises(InvariantViolation):
            vectorize(other, poly.index)


class TestLoadBearingStructure:
    """`A_eq` shape — see ADR-7 and tests/unit/test_load_bearing.py."""

    def test_a_eq_is_empty_but_well_shaped(self) -> None:
        """Load-bearing walls are inequality rows (``RelativeOrder.wall_sides``), not
        equalities: ``A_eq`` stays empty but correctly shaped (ADR-7)."""
        poly = build_polytope(ORDER_AB, CTX)
        assert poly.A_eq.shape == (0, len(poly.index))
        assert poly.b_eq.shape == (0,)


class TestRefusals:
    """No inconsistent dimension passes silently."""

    def test_contains_refuses_an_inconsistent_dimension(self) -> None:
        """A vector of the wrong size is a matching bug, not a point outside the domain."""
        poly = build_polytope(ORDER_AB, CTX)
        with pytest.raises(InvariantViolation, match="shape"):
            poly.contains(np.zeros(3))

    def test_devectorize_refuses_an_inconsistent_dimension(self) -> None:
        """Same rule at the solver output."""
        poly = build_polytope(ORDER_AB, CTX)
        with pytest.raises(InvariantViolation, match="shape"):
            devectorize(np.zeros(3), PLAN_AB, poly.index)

    def test_devectorize_refuses_a_room_outside_the_polytope(self) -> None:
        """Leaving a room not updated would produce a false plan.

        The defect would be caught further on by ``certify``, but with a diagnostic
        unrelated to its cause: the worst of both worlds.
        """
        poly = build_polytope(ORDER_AB, CTX)
        foreign = Plan(
            rooms=(*PLAN_AB.rooms, Room(id="Z", type="toilet", x=0.0, y=0.0, w=1.0, h=1.0)),
            walls=(),
            openings=(),
            outline=CTX.outline,
        )
        with pytest.raises(InvariantViolation, match="Z"):
            devectorize(vectorize(PLAN_AB, poly.index), foreign, poly.index)

    def test_contains_also_checks_the_equalities(self) -> None:
        """``A_eq`` is empty today, but ``contains`` must know how to handle it.

        The day ADR-7 is settled, this branch will carry the load-bearing structure;
        leaving it untested until then would mean discovering it in production.
        """
        poly = build_polytope(ORDER_AB, CTX)
        row = sparse.csr_matrix(([1.0], ([0], [poly.index["A.x"]])), shape=(1, len(poly.index)))
        point = vectorize(PLAN_AB, poly.index)  # A.x is 0

        # Two variants of the same polytope: only the right-hand side changes, so that
        # both branches are comparable, all else being equal.
        assert replace(poly, A_eq=row, b_eq=np.array([0.0])).contains(point)
        assert not replace(poly, A_eq=row, b_eq=np.array([3.0])).contains(point)

    def test_a_flat_outline_is_refused(self) -> None:
        """An outline of zero area would give empty bounds without saying so."""
        ctx = Context(
            structure=Structure(load_bearing_walls=()),
            orientation=Orientation(deg=0.0),
            outline=((0.0, 0.0), (10.0, 0.0), (10.0, 0.0)),
            regulation=Regulation(min_areas=()),
        )
        with pytest.raises(InvariantViolation, match="degenerate"):
            build_polytope(ORDER_AB, ctx)


def test_a_degenerate_outline_is_refused() -> None:
    """An empty outline has no envelope: say so rather than produce zero bounds."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=(),
        regulation=Regulation(min_areas=()),
    )
    with pytest.raises(InvariantViolation):
        build_polytope(ORDER_AB, ctx)


def test_freeze_contacts_forbids_a_gap() -> None:
    """A saturated tiling, once frozen, no longer allows rooms to move apart."""
    from archlux.geom.graph import deduce_order

    poly = build_polytope(deduce_order(PLAN_AB), CTX)
    x = vectorize(PLAN_AB, poly.index)
    tight = freeze_contacts(poly, x)
    assert tight.A_eq.shape[0] > poly.A_eq.shape[0]
    assert tight.contains(x)
    apart = x.copy()
    apart[poly.index["B.x"]] += 0.5
    apart[poly.index["B.w"]] -= 0.5
    assert poly.contains(apart)
    assert not tight.contains(apart)
    left_gap = x.copy()
    left_gap[poly.index["A.x"]] += 0.2
    left_gap[poly.index["A.w"]] -= 0.2
    assert poly.contains(left_gap)
    assert not tight.contains(left_gap)
