"""Model types are keyword-only where positions are easy to swap, with light defaults.

PLAN.md 3.6. ``Piece("a", "sejour", 0, 0, 6, 9)`` swapped ``x, y, w, h`` without error;
``Plan`` needed ``murs=()`` and ``ouvertures=()`` even for a plan without walls; and the
outline had to be given twice, in the ``Plan`` and in the ``Contexte``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from archlux import (
    Contexte,
    InvalidInput,
    Mur,
    Orientation,
    Ouverture,
    Piece,
    Plan,
    Referentiel,
    Structure,
    legalize,
)

SQUARE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def rooms() -> tuple[Piece, ...]:
    return (
        Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
        Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
    )


def test_piece_refuses_positional_arguments() -> None:
    with pytest.raises(TypeError):
        Piece("a", "sejour", 0.0, 0.0, 6.0, 9.0)  # type: ignore[misc]


def test_wall_refuses_positional_arguments() -> None:
    with pytest.raises(TypeError):
        Mur("m", (0.0, 0.0), (1.0, 0.0))  # type: ignore[misc]


def test_opening_refuses_positional_arguments() -> None:
    with pytest.raises(TypeError):
        Ouverture("o", "m", 0.5, 0.2)  # type: ignore[misc]


def test_a_plan_needs_only_its_rooms() -> None:
    plan = Plan(pieces=rooms())
    assert plan.murs == ()
    assert plan.ouvertures == ()
    assert plan.contour == ()
    assert plan.certificat is None


def test_the_plan_keeps_its_positional_order() -> None:
    """Only the three types above became keyword-only: existing ``Plan(...)`` calls hold."""
    plan = Plan(rooms(), (), (), SQUARE)
    assert plan.contour == SQUARE


def context(**changes: object) -> Contexte:
    base = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        referentiel=Referentiel(aires_min=(), largeur_min=1.0),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_the_context_outline_defaults_to_empty() -> None:
    assert context().contour == ()


def test_legalize_reads_the_outline_from_the_plan() -> None:
    legal = legalize(Plan(pieces=rooms(), contour=SQUARE), context())
    assert legal.contour == SQUARE
    assert legal.certificat is not None
    assert legal.certificat.geometrie.valide


def test_legalize_reads_the_outline_from_the_context() -> None:
    legal = legalize(Plan(pieces=rooms()), context(contour=SQUARE))
    assert legal.contour == SQUARE
    assert legal.certificat is not None
    assert legal.certificat.geometrie.valide


def test_the_context_outline_wins_when_both_are_given() -> None:
    other = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0), (0.0, 9.0))
    legal = legalize(Plan(pieces=rooms(), contour=other), context(contour=SQUARE))
    assert legal.contour == SQUARE


def test_no_outline_anywhere_is_refused_with_the_fix() -> None:
    with pytest.raises(InvalidInput, match=r"Contexte.contour") as raised:
        legalize(Plan(pieces=rooms()), context())
    assert raised.value.field == "contour"


def test_a_two_point_outline_is_still_refused() -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(Plan(pieces=rooms(), contour=((0.0, 0.0), (1.0, 0.0))), context())
    assert raised.value.field == "contour"
