"""Recovery of the tiling grid from a nearly valid plan (``legalize(..., pavage=True)``).

The faulty cases come from the guarantee benchmark (``benchmarks/guarantees``), modes
``classic_noisy`` and ``partial_one_fault``. They are written out as literals so that
the test does not depend on the generator. Inputs the grid cannot describe are refused
with a typed input error, never with ``InvariantViole`` (reserved for internal bugs).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import archlux
from archlux.geom.pavage import deduire_trame
from archlux.types import Contexte, Mur, Orientation, Piece, Plan, Referentiel, Structure
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


def test_a_room_overlapping_a_neighbour_on_both_axes_keeps_the_grid_relation() -> None:
    """Benchmark mode ``partial_one_fault``: ``r4`` is moved 25 cm left, onto ``r7``.

    The two rooms then overlap on both axes, and their centres alone would put ``r4``
    *below* ``r7``. The recovered grid knows better: ``r4`` is to the right of ``r7``.
    The partial load-bearing wall pins the line between ``r6`` and ``r7``, so the wrong
    relation cannot be absorbed by collapsing a grid line.
    """
    outline = ((0.0, 0.0), (13.3, 0.0), (13.3, 10.4), (0.0, 10.4))
    wall = Mur(id="refend", a=(0.0, 2.6), b=(3.2, 2.6), porteur=True)
    kinds = {
        "r0": "sejour",
        "r1": "couloir",
        "r2": "chambre",
        "r3": "sdb",
        "r4": "couloir",
        "r5": "chambre",
        "r6": "wc",
        "r7": "chambre",
    }
    edges = {
        "r0": (11.1, 3.6, 13.3, 10.4),
        "r1": (3.2, 3.6, 5.5, 10.4),
        "r2": (5.5, 3.6, 11.1, 8.4),
        "r3": (5.5, 8.4, 11.1, 10.4),
        "r4": (2.95, 0.0, 5.85, 3.6),
        "r5": (6.1, 0.0, 13.3, 3.6),
        "r6": (0.0, 0.0, 3.2, 2.6),
        "r7": (0.0, 2.6, 3.2, 10.4),
    }
    rooms = tuple(replace(_room(name, *edges[name]), type=kind) for name, kind in kinds.items())
    plan = Plan(pieces=rooms, murs=(wall,), ouvertures=(), contour=outline)
    ctx = replace(
        _context(outline),
        structure=Structure(murs_porteurs=(wall,)),
        referentiel=Referentiel(
            aires_min=(
                ("chambre", 20.5806),
                ("couloir", 8.6082),
                ("sdb", 9.2349),
                ("sejour", 12.3352),
                ("wc", 6.8602),
            ),
            largeur_min=1.0,
        ),
    )
    result = archlux.legalize(plan, ctx, pavage=True)
    assert checkers.violations(result, ctx) == []
    by_id = {room.id: room for room in result.pieces}
    assert by_id["r4"].x == pytest.approx(by_id["r7"].x + by_id["r7"].w)


def test_outer_grid_lines_lie_exactly_on_the_outline() -> None:
    grid = deduire_trame(NOISY_RIGHT_EDGE, _context())
    assert grid.lignes_x[0] == 0.0
    assert grid.lignes_x[-1] == WIDTH
    assert grid.lignes_y[0] == 0.0
    assert grid.lignes_y[-1] == HEIGHT
