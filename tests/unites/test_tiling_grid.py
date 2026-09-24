"""Recovery of the tiling grid from a nearly valid plan (``legalize(..., pavage=True)``).

The cases come from the guarantee benchmark (``benchmarks/guarantees``), mode
``classic_noisy``: every coordinate moved by a few centimetres. They are written out as
literals so that the test does not depend on the generator.
"""

from __future__ import annotations

import archlux
from archlux.geom.pavage import deduire_trame
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure
from tests import checkers

WIDTH = 11.0
HEIGHT = 7.8
OUTLINE = ((0.0, 0.0), (WIDTH, 0.0), (WIDTH, HEIGHT), (0.0, HEIGHT))


def _context(outline: tuple[tuple[float, float], ...] = OUTLINE) -> Contexte:
    return Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(), largeur_min=1.0),
    )


def _plan(*rooms: Piece, outline: tuple[tuple[float, float], ...] = OUTLINE) -> Plan:
    return Plan(pieces=rooms, murs=(), ouvertures=(), contour=outline)


def _room(name: str, left: float, bottom: float, right: float, top: float) -> Piece:
    return Piece(id=name, type="sejour", x=left, y=bottom, w=right - left, h=top - bottom)


# Two right edges fall a few millimetres on each side of the outline edge at x = 11:
# grouped with it, they must not pull the outer grid line off the outline.
NOISY_RIGHT_EDGE = _plan(
    _room("a", 0.0, 0.0, 5.5, HEIGHT),
    _room("b", 5.5, 0.0, 10.9957, 3.9),
    _room("c", 5.5, 3.9, 11.0035, HEIGHT),
)


def test_tiling_legalization_of_a_noisy_edge_keeps_every_guarantee() -> None:
    result = archlux.legalize(NOISY_RIGHT_EDGE, _context(), pavage=True)
    assert result.certificat is not None
    assert result.certificat.geometrie.valide
    assert checkers.violations(result, _context()) == []


def test_outer_grid_lines_lie_exactly_on_the_outline() -> None:
    grid = deduire_trame(NOISY_RIGHT_EDGE, _context())
    assert grid.lignes_x[0] == 0.0
    assert grid.lignes_x[-1] == WIDTH
    assert grid.lignes_y[0] == 0.0
    assert grid.lignes_y[-1] == HEIGHT
