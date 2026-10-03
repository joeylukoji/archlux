"""Geometric diagnostic: quantify *how* a plan is invalid.

These tests pin the five quantities that decide whether `legalize` stands a chance on a
given input. They use hand-built cases whose expected value can be computed mentally: a
diagnostic whose output cannot be recomputed is useless to characterize a corpus.
"""

from __future__ import annotations

import pytest

from archlux.geom.diagnostic import Diagnostic, diagnose
from archlux.types import Plan, Room


def _plan(*boxes: tuple[float, float, float, float]) -> Plan:
    """Plan without walls or outline, one room per ``(x, y, w, h)``."""
    return Plan(
        rooms=tuple(
            Room(id=f"p{i}", type="salon", x=x, y=y, w=w, h=h)
            for i, (x, y, w, h) in enumerate(boxes)
        ),
        walls=(),
        openings=(),
        outline=(),
    )


def test_an_exact_tiling_shows_no_pathology() -> None:
    """Two adjoining rooms: nothing to report, and the grid has 2 cells."""
    diag = diagnose(_plan((0.0, 0.0, 3.0, 2.0), (3.0, 0.0, 2.0, 2.0)))
    assert diag == Diagnostic(
        overlaps=0.0,
        gap_share=0.0,
        hole_share=0.0,
        fragments=1,
        cells=2,
        size=pytest.approx(10.0**0.5),
    )


def test_overlap_is_counted_both_ways() -> None:
    """Two overlapping rooms each overlap one: mean 1.0.

    Counting the pair once would give 0.5 and would no longer be comparable with the
    figure published by the MSD authors (4.11 overlapped rooms per room).
    """
    diag = diagnose(_plan((0.0, 0.0, 3.0, 2.0), (2.0, 0.0, 3.0, 2.0)))
    assert diag.overlaps == 1.0


def test_an_edge_contact_does_not_count_as_overlap() -> None:
    """Two neighbouring rooms share an edge of zero area, not a surface."""
    assert diagnose(_plan((0.0, 0.0, 3.0, 2.0), (3.0, 0.0, 2.0, 2.0))).overlaps == 0.0


def test_a_boundary_gap_is_not_an_interior_hole() -> None:
    """The distinction is the heart of the module: here a gap, no hole.

    Without it, the generator is blamed for a defect that may only be the choice of a
    rectangular bounding box over an L-shaped footprint.
    """
    diag = diagnose(_plan((0.0, 0.0, 2.0, 2.0), (2.0, 2.0, 2.0, 2.0)))
    assert diag.gap_share == pytest.approx(0.5)
    assert diag.hole_share == 0.0
    # They touch only at a corner: two components, not one. That is the right
    # semantics here: a shared corner is neither a party wall nor a passage, and for
    # the tiling it remains a gap.
    assert diag.fragments == 2


def test_a_closed_hole_is_counted_twice() -> None:
    """A ring of four rooms: the central hole counts as a gap **and** as a hole."""
    diag = diagnose(
        _plan(
            (0.0, 0.0, 3.0, 1.0),  # bottom
            (0.0, 2.0, 3.0, 1.0),  # top
            (0.0, 1.0, 1.0, 1.0),  # left
            (2.0, 1.0, 1.0, 1.0),  # right
        )
    )
    assert diag.hole_share == pytest.approx(1.0 / 9.0)
    assert diag.gap_share == pytest.approx(diag.hole_share)


def test_separate_rooms_form_an_archipelago() -> None:
    """The number of fragments is what tells a damaged plan from an absent one.

    Three disjoint rooms are not an apartment to repair: no grid will catch them up at a
    reasonable budget. That is the regime observed on the outputs of HouseDiffusion
    (`results/j8_*.md`).
    """
    diag = diagnose(_plan((0.0, 0.0, 1.0, 1.0), (3.0, 0.0, 1.0, 1.0), (6.0, 0.0, 1.0, 1.0)))
    assert diag.fragments == 3
    assert diag.overlaps == 0.0


def test_cells_explode_when_no_edge_coincides() -> None:
    """Three rooms aligned on the same lines: 3 cells. Shifted: 25.

    This measure says whether the combinatorial structure of the tiling exists. On a
    real plan the rooms share their walls; on a model output, almost no coordinate
    coincides and the grid swells.
    """
    aligned = diagnose(_plan((0.0, 0.0, 1.0, 2.0), (1.0, 0.0, 1.0, 2.0), (2.0, 0.0, 1.0, 2.0)))
    shifted = diagnose(_plan((0.0, 0.0, 1.0, 2.0), (1.3, 0.4, 1.1, 2.0), (2.7, 0.9, 1.2, 2.0)))
    assert aligned.cells == 3
    assert shifted.cells == 25


def test_the_size_gives_the_scale_of_the_displacement() -> None:
    """``size`` is the square root of the bounding area: 5 m reads differently on 10 m."""
    assert diagnose(_plan((0.0, 0.0, 4.0, 9.0))).size == pytest.approx(6.0)


def test_a_plan_without_rooms_raises() -> None:
    """Returning zeros would suggest a sound plan: it is refused."""
    with pytest.raises(ValueError, match="nothing to diagnose"):
        diagnose(_plan())


@pytest.mark.parametrize("factor", [0.1, 1.0, 7.5])
def test_the_shares_are_scale_invariant(factor: float) -> None:
    """Gap, hole and overlap are ratios: metres do not enter them.

    That is what allows comparing RPLAN plans (unitless) with MSD plans in metres, and
    what makes the scale choice of milestone 8 irrelevant to the reported rates.
    """
    boxes = ((0.0, 0.0, 2.0, 2.0), (1.0, 2.0, 2.0, 2.0))
    reference = diagnose(_plan(*boxes))
    scaled = diagnose(
        _plan(*((x * factor, y * factor, w * factor, h * factor) for x, y, w, h in boxes))
    )
    assert scaled.gap_share == pytest.approx(reference.gap_share)
    assert scaled.hole_share == pytest.approx(reference.hole_share)
    assert scaled.overlaps == reference.overlaps
    assert scaled.size == pytest.approx(reference.size * factor)
