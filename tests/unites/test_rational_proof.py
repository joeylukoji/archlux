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


@pytest.mark.parametrize("width", [1e-9, 3e-8])
def test_a_sliver_below_the_tolerance_is_not_an_overlap(width: float) -> None:
    """A float sliver from the LP noise must not fail an otherwise exact tiling."""
    plan = _plan(_room("a", 0.0, 0.0, 0.3 + width, 1.0), _room("b", 0.3, 0.0, 0.3, 1.0))
    assert verify_exactly(plan, _ctx()).valide
