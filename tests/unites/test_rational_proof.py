"""Tiling proved in exact rational arithmetic (PLAN.md batch 1.5b, AUDIT.md §5.4).

Edges closer than ``SNAP_M`` (1e-7 m) are identified: that is the only tolerance, on
lengths. Everything else is exact (``fractions.Fraction``): pairwise disjoint interiors,
inclusion in the outline, and the sum of room areas equal to the outline area, which
together imply that the rooms tile the outline.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from archlux.certify.proof import rational_tiling, verify_exactly
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides

_OUTLINE = ((0.0, 0.0), (0.6, 0.0), (0.6, 1.0), (0.0, 1.0))


def _ctx(outline: tuple[tuple[float, float], ...] = _OUTLINE) -> Contexte:
    return Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(), largeur_min=0.05),
    )


def _plan(*rooms: Piece, outline: tuple[tuple[float, float], ...] = _OUTLINE) -> Plan:
    return Plan(pieces=rooms, murs=(), ouvertures=(), contour=outline)


def _room(rid: str, x: float, y: float, w: float, h: float) -> Piece:
    return Piece(id=rid, type="chambre", x=x, y=y, w=w, h=h)


def test_decimal_inputs_tile_exactly_despite_binary_floats() -> None:
    """0.1 + 0.2 != 0.3 in binary floating point; the identified edges make it exact."""
    plan = _plan(
        _room("a", 0.0, 0.0, 0.1, 1.0),
        _room("b", 0.1, 0.0, 0.2, 1.0),
        _room("c", 0.3, 0.0, 0.3, 1.0),
    )
    assert 0.1 + 0.2 != 0.3
    assert rational_tiling(plan, _ctx()) == ()


def test_a_real_overlap_is_reported_with_its_exact_area() -> None:
    plan = _plan(_room("a", 0.0, 0.0, 0.35, 1.0), _room("b", 0.3, 0.0, 0.3, 1.0))
    (violation, *_) = rational_tiling(plan, _ctx())
    assert violation.startswith("overlap a|b:")


def test_a_gap_wider_than_the_identification_tolerance_is_reported() -> None:
    plan = _plan(_room("a", 0.0, 0.0, 0.3, 1.0), _room("b", 0.3 + 1e-6, 0.0, 0.3 - 1e-6, 1.0))
    assert any(v.startswith("gap:") for v in rational_tiling(plan, _ctx()))


def test_edges_closer_than_the_tolerance_are_the_same_line() -> None:
    plan = _plan(_room("a", 0.0, 0.0, 0.3, 1.0), _room("b", 0.3 + 5e-8, 0.0, 0.3 - 5e-8, 1.0))
    assert rational_tiling(plan, _ctx()) == ()


def test_a_room_outside_the_outline_is_reported() -> None:
    plan = _plan(_room("a", 0.0, 0.0, 0.3, 1.0), _room("b", 0.3, 0.0, 0.4, 1.0))
    assert any("outside the outline" in v for v in rational_tiling(plan, _ctx()))


def test_a_non_rectangular_outline_is_not_handled_rationally() -> None:
    l_shape = ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0))
    plan = _plan(_room("a", 0.0, 0.0, 2.0, 1.0), _room("b", 0.0, 1.0, 1.0, 1.0), outline=l_shape)
    assert rational_tiling(plan, _ctx(l_shape)) is None


@settings(max_examples=300, deadline=None, derandomize=True)
@given(plan=plans_valides())
def test_every_guillotine_tiling_passes_the_rational_check(plan: Plan) -> None:
    assert rational_tiling(plan, CONTEXTE_DEFAUT) == ()


def test_the_proof_uses_the_rational_check_on_rectangular_outlines() -> None:
    overlap = _plan(_room("a", 0.0, 0.0, 0.35, 1.0), _room("b", 0.3, 0.0, 0.3, 1.0))
    proof = verify_exactly(overlap, _ctx())
    assert not proof.valide and proof.chevauchement
    assert any(v.startswith("overlap a|b:") for v in proof.violations)


@pytest.mark.parametrize("width", [1e-10, 5e-10])
def test_a_sliver_below_the_tolerance_is_not_an_overlap(width: float) -> None:
    """A float sliver from the LP noise must not fail an otherwise exact tiling."""
    plan = _plan(_room("a", 0.0, 0.0, 0.3 + width, 1.0), _room("b", 0.3, 0.0, 0.3, 1.0))
    assert verify_exactly(plan, _ctx()).valide


def test_a_sliver_above_the_overlap_tolerance_is_refused() -> None:
    """Review M2: 3e-8 m x 1 m = 3e-8 m2 exceeds OVERLAP_M2, as it did before batch 1.5b."""
    plan = _plan(_room("a", 0.0, 0.0, 0.3 + 3e-8, 1.0), _room("b", 0.3, 0.0, 0.3, 1.0))
    proof = verify_exactly(plan, _ctx())
    assert not proof.valide and proof.chevauchement


# --- Review of batch 1.5 -------------------------------------------------------------


def test_a_program_that_fills_the_outline_exactly_is_still_legalized() -> None:
    """Review M1: two 4.5 m² bedrooms in 3 m x 3 m leave no room for an area margin.

    Batch 1.5a aimed every deficit room 1e-6 m² above its minimum and refused this
    feasible program with InvariantViole; the loop must fall back on the exact minimum.
    """
    import archlux

    outline = ((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0))
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(("chambre", 4.5),), largeur_min=0.5),
    )
    plan = _plan(_room("a", 0.0, 0.0, 1.0, 3.0), _room("b", 1.0, 0.0, 2.0, 3.0), outline=outline)
    result = archlux.legalize(plan, ctx)
    assert result.certificat is not None and result.certificat.geometrie.valide
    widths = sorted(round(room.w, 6) for room in result.pieces)
    assert widths == [1.5, 1.5]


def test_the_proof_bounds_what_edge_identification_erases() -> None:
    """Review M2: a 0.9e-7 m gap along 100 m is 9e-6 m² of uncovered floor. Identifying
    the edges must not hide it: the erased area stays bounded by the area tolerances."""
    outline = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    plan = _plan(
        _room("a", 0.0, 0.0, 50.0, 100.0),
        _room("b", 50.0 + 0.9e-7, 0.0, 50.0 - 0.9e-7, 100.0),
        outline=outline,
    )
    proof = verify_exactly(plan, _ctx(outline))
    assert not proof.valide and proof.jours


_L_SHAPE = ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0))


def test_the_geos_path_accepts_a_tiling_of_a_non_rectangular_outline() -> None:
    """Review minor 6: outlines that are not rectangles go through GEOS; pin that path."""
    plan = _plan(_room("a", 0.0, 0.0, 2.0, 1.0), _room("b", 0.0, 1.0, 1.0, 1.0), outline=_L_SHAPE)
    assert verify_exactly(plan, _ctx(_L_SHAPE)).valide


@pytest.mark.parametrize(
    ("rooms", "overlap", "gaps"),
    [
        ((("a", 0.0, 0.0, 2.0, 1.0), ("b", 0.0, 0.5, 1.0, 1.5)), True, False),
        ((("a", 0.0, 0.0, 2.0, 1.0), ("b", 0.0, 1.0, 1.0, 0.5)), False, True),
        ((("a", 0.0, 0.0, 2.0, 1.0), ("b", 0.0, 1.0, 1.5, 1.0)), False, True),
    ],
    ids=["overlap", "uncovered", "overhang"],
)
def test_the_geos_path_detects_faults_on_a_non_rectangular_outline(
    rooms: tuple[tuple[str, float, float, float, float], ...], overlap: bool, gaps: bool
) -> None:
    plan = _plan(*(_room(*room) for room in rooms), outline=_L_SHAPE)
    proof = verify_exactly(plan, _ctx(_L_SHAPE))
    assert not proof.valide
    assert (proof.chevauchement, proof.jours) == (overlap, gaps)
