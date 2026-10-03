"""Exact tiling constraints: `geom.tiling`.

The thesis of the module: the tiling condition is **combinatorial**. It only bears on
the edge/line incidences, never on the coordinates. These tests pin that property, and
the fact that a gap becomes unrepresentable.
"""

from __future__ import annotations

import numpy as np
import pytest

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.errors import GridNotRecoverable, UnsupportedInput
from archlux.geom.tiling import deduce_grid
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure

_RECT = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def _ctx(outline: tuple[tuple[float, float], ...] = _RECT) -> Context:
    return Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=0.0),
    )


def _tiling_2x2(sw_width: float = 5.0) -> Plan:
    """2x2 tiling; `sw_width` < 5 opens a gap under the north-west room."""
    return Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=sw_width, h=4.0),
            Room(id="se", type="bedroom", x=5.0, y=0.0, w=7.0, h=4.0),
            Room(id="nw", type="kitchen", x=0.0, y=4.0, w=5.0, h=5.0),
            Room(id="ne", type="bathroom", x=5.0, y=4.0, w=7.0, h=5.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )


def _pinwheel() -> Plan:
    """Pinwheel: 5 rectangles, a **non-sliceable** dissection."""
    outline = ((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))
    return Plan(
        rooms=(
            Room(id="A", type="living_room", x=0.0, y=6.0, w=6.0, h=3.0),
            Room(id="B", type="living_room", x=6.0, y=3.0, w=3.0, h=6.0),
            Room(id="C", type="living_room", x=3.0, y=0.0, w=6.0, h=3.0),
            Room(id="D", type="living_room", x=0.0, y=0.0, w=3.0, h=6.0),
            Room(id="E", type="living_room", x=3.0, y=3.0, w=3.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=outline,
    )


def test_grid_of_a_sound_tiling() -> None:
    """The lines are the shared edges, not one edge per room."""
    grid = deduce_grid(_tiling_2x2(), _ctx())
    assert grid.x_lines == (0.0, 5.0, 12.0)
    assert grid.y_lines == (0.0, 4.0, 9.0)
    assert grid.n_cells == 4


def test_a_non_sliceable_dissection_is_accepted() -> None:
    """The pinwheel cannot be cut by any guillotine cut.

    It is the case that tells a real tiling condition from a sliceability
    assumption: the 9 cells do form a partition.
    """
    grid = deduce_grid(_pinwheel(), _ctx(((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))))
    assert grid.n_cells == 9
    assert len(grid.incidences) == 5


def test_a_rectilinear_outline_is_accepted() -> None:
    """An L-shaped outline: the cells outside the outline must stay empty.

    Requiring a tiling of the **bounding box** would reject every real apartment.
    """
    outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 4.0), (5.0, 4.0), (5.0, 9.0), (0.0, 9.0))
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=5.0, h=4.0),
            Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=4.0),
            Room(id="c", type="kitchen", x=0.0, y=4.0, w=5.0, h=5.0),
        ),
        walls=(),
        openings=(),
        outline=outline,
    )
    grid = deduce_grid(plan, _ctx(outline))
    assert grid.x_lines == (0.0, 5.0, 12.0)
    # Every line carries an outline vertex: none can slide.
    assert grid.anchored_x == frozenset({0, 1, 2})


@pytest.mark.parametrize("gap", [0.05, 0.5, 2.0])
def test_the_support_recovers_the_grid_whatever_the_amplitude(gap: float) -> None:
    """An orphan line is absorbed, without any threshold in metres.

    That is what tells the support criterion from a metric tolerance: a 2 m gap is
    caught as well as a 5 cm gap.
    """
    grid = deduce_grid(_tiling_2x2(sw_width=5.0 - gap), _ctx())
    assert grid.x_lines == (0.0, 5.0, 12.0)


def test_a_narrow_partition_is_not_crushed() -> None:
    """The refusal to crush a room bounds the consolidation."""
    plan = Plan(
        rooms=(
            Room(id="corridor", type="corridor", x=0.0, y=0.0, w=0.4, h=9.0),
            Room(id="living_room", type="living_room", x=0.4, y=0.0, w=11.6, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    assert deduce_grid(plan, _ctx()).x_lines == (0.0, 0.4, 12.0)


def _three_rooms_out_of_four() -> Plan:
    """2x2 tiling without its north-east room: one cell stays empty."""
    return Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=5.0, h=4.0),
            Room(id="se", type="bedroom", x=5.0, y=0.0, w=7.0, h=4.0),
            Room(id="nw", type="kitchen", x=0.0, y=4.0, w=5.0, h=5.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )


def test_a_structural_gap_is_detected_without_budget() -> None:
    """`repair_budget=0`: the partition is checked, never touched up."""
    with pytest.raises(GridNotRecoverable, match="uncovered"):
        deduce_grid(_three_rooms_out_of_four(), _ctx(), repair_budget=0)


def test_a_missing_room_is_absorbed_by_its_neighbour() -> None:
    """A semantic consequence to know: the programme changes.

    With the default budget, the empty cell is given to a neighbouring room rather
    than refused. That is the expected behaviour of a legalizer (closing a gap means
    enlarging someone), but the plan comes out with **one room fewer** than the
    generator intended. A caller who must preserve the programme room by room passes
    `repair_budget=0`.
    """
    plan = _three_rooms_out_of_four()
    grid = deduce_grid(plan, _ctx())
    areas = {inc[0]: (inc[2] - inc[1]) * (inc[4] - inc[3]) for inc in grid.incidences}
    assert sum(areas.values()) == grid.n_cells  # the grid is entirely covered
    assert len(grid.incidences) == 3

    fixed = ax.legalize(plan, _ctx(), tiling=True)
    assert fixed.certificate is not None
    assert fixed.certificate.geometry.valid
    assert len(fixed.rooms) == 3


def test_the_budget_bounds_the_repair() -> None:
    """Beyond the budget, the fault is no longer a wrong dimension: it is refused."""
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=2.0, h=3.0),
            Room(id="b", type="bedroom", x=4.0, y=6.0, w=2.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    with pytest.raises(GridNotRecoverable):
        deduce_grid(plan, _ctx(), repair_budget=1)


@pytest.mark.parametrize("budget", [0, 1, 2, 4, 8])
@pytest.mark.parametrize("damage", [0.05, 0.5, 2.0, 6.0])
def test_every_returned_grid_is_a_valid_partition(budget: int, damage: float) -> None:
    """Central property: `deduce_grid` refuses, or returns an exact partition.

    It must **never** return a half-repaired structure: no empty cell, no doubly
    covered cell, no room with inverted edges. That property is what allows
    `extend_tiling` to guarantee the tiling without a check at run time.
    """
    plan = _tiling_2x2(sw_width=max(0.5, 5.0 - damage))
    try:
        grid = deduce_grid(plan, _ctx(), repair_budget=budget)
    except GridNotRecoverable:
        return  # explicit refusal: the other branch of the contract
    cells = np.zeros((len(grid.x_lines) - 1, len(grid.y_lines) - 1), dtype=int)
    for name, left, right, low, high in grid.incidences:
        assert left < right, f"{name} has inverted edges in x"
        assert low < high, f"{name} has inverted edges in y"
        cells[left:right, low:high] += 1
    assert np.all(cells == 1), "the returned grid is not a partition"


def test_repair_does_not_change_a_sound_plan() -> None:
    """On an already exact partition, no touch-up is applied."""
    sound = deduce_grid(_tiling_2x2(), _ctx(), repair_budget=0)
    with_repair = deduce_grid(_tiling_2x2(), _ctx(), repair_budget=8)
    assert sound == with_repair


def test_a_simple_overlap_is_absorbed_by_the_support() -> None:
    """Two overlapping orphan edges merge on a common line.

    That is the intended behaviour: a 2 m overlap between two neighbouring rooms is a
    badly dimensioned adjacency intent, not an order inconsistency.
    """
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
            Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    grid = deduce_grid(plan, _ctx())
    assert len(grid.x_lines) == 3
    spans = {inc[0]: inc[1:3] for inc in grid.incidences}
    assert spans["a"][1] == spans["b"][0]  # a ends where b starts


def test_a_structural_overlap_is_refused() -> None:
    """A room **contained** in another: no line merge saves it."""
    plan = Plan(
        rooms=(
            Room(id="enclosing", type="living_room", x=0.0, y=0.0, w=12.0, h=9.0),
            Room(id="enclosed", type="bedroom", x=0.0, y=0.0, w=5.0, h=4.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    with pytest.raises(GridNotRecoverable, match="covered twice"):
        deduce_grid(plan, _ctx())


def test_legalize_with_tiling_closes_a_gap() -> None:
    """The case that `legalize` alone cannot fix.

    Without `tiling=True`, the plan with a hole is already the closest to itself: the
    L1 optimum leaves it as is and the exact check rejects it.
    """
    damaged = _tiling_2x2(sw_width=4.5)
    ctx = _ctx()
    assert not verify_exactly(damaged, ctx).valid

    with pytest.raises(ax.GapNeedsTiling, match="tiling=True"):
        ax.legalize(damaged, ctx)

    fixed = ax.legalize(damaged, ctx, tiling=True)
    assert fixed.certificate is not None
    assert fixed.certificate.geometry.valid
    assert not fixed.certificate.geometry.gaps


def test_tiling_preserves_idempotence() -> None:
    """On an already valid plan, `tiling=True` moves nothing."""
    ctx = _ctx()
    fixed = ax.legalize(_tiling_2x2(), ctx, tiling=True)
    assert fixed.certificate is not None
    assert fixed.certificate.geometry.max_displacement == pytest.approx(0.0, abs=1e-9)


def test_tiling_is_invariant_under_line_translation() -> None:
    """The thesis of the module: the condition only bears on the incidences.

    Two plans with the same combinatorial structure but different coordinates have the
    same grid in indices, and both are valid tilings.
    """
    ctx = _ctx()
    a = deduce_grid(_tiling_2x2(), ctx)
    shifted = Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=3.0, h=6.0),
            Room(id="se", type="bedroom", x=3.0, y=0.0, w=9.0, h=6.0),
            Room(id="nw", type="kitchen", x=0.0, y=6.0, w=3.0, h=3.0),
            Room(id="ne", type="bathroom", x=3.0, y=6.0, w=9.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    b = deduce_grid(shifted, ctx)
    assert [inc[1:] for inc in a.incidences] == [inc[1:] for inc in b.incidences]
    assert a.x_lines != b.x_lines
    assert verify_exactly(shifted, ctx).valid


def test_tiling_equalities_do_not_pollute_the_dual_diagnostic() -> None:
    """Tiling constraints are equalities: they are not dualized."""
    ctx = _ctx()
    plain = ax.legalize(_tiling_2x2(), ctx)
    tiled = ax.legalize(_tiling_2x2(), ctx, tiling=True)
    assert plain.certificate is not None
    assert tiled.certificate is not None
    labels = {label for label, _ in tiled.certificate.duals}
    assert not any(name.startswith(("trame ", "contour ")) for name in labels)


def test_a_plan_without_rooms_is_refused() -> None:
    """A typed error, never a bare IndexError."""
    empty = Plan(rooms=(), walls=(), openings=(), outline=_RECT)
    with pytest.raises(UnsupportedInput, match="no room"):
        deduce_grid(empty, _ctx())


def test_the_grid_is_deterministic() -> None:
    """Two calls on the same plan return exactly the same grid."""
    plan = _tiling_2x2(sw_width=4.7)
    a = deduce_grid(plan, _ctx())
    b = deduce_grid(plan, _ctx())
    assert a == b
    assert np.allclose(a.x_lines, b.x_lines)
