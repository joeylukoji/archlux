"""SVG rendering (export.svg had no test at all, AUDIT.md Q-M7)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from archlux.export.svg import comparer, rendre
from archlux.types import Mur, Piece, Plan

_OUTLINE = ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0))
_ROOMS = (
    Piece(id="a", type="sejour", x=0.0, y=0.0, w=2.0, h=2.0),
    Piece(id="b", type="chambre", x=2.0, y=0.0, w=2.0, h=2.0),
)
_BEARING = Mur(id="lb", a=(2.0, 0.0), b=(2.0, 2.0), porteur=True)
_PARTITION = Mur(id="p", a=(0.0, 1.0), b=(2.0, 1.0), porteur=False)


def _plan(*walls: Mur) -> Plan:
    return Plan(pieces=_ROOMS, murs=walls, ouvertures=(), contour=_OUTLINE)


def _lines(svg: str, css_class: str) -> list[ET.Element]:
    root = ET.fromstring(svg)
    return [e for e in root.iter() if e.tag.endswith("line") and e.get("class") == css_class]


def test_the_document_is_well_formed_svg() -> None:
    root = ET.fromstring(rendre(_plan(), titre="t"))
    assert root.tag.endswith("svg")


def test_every_room_is_drawn() -> None:
    svg = rendre(_plan())
    assert len(re.findall(r"<rect ", svg)) == 2 + len(_ROOMS)  # background + frame + rooms


def test_load_bearing_walls_are_drawn_and_distinguishable() -> None:
    svg = rendre(_plan(_BEARING, _PARTITION))
    bearing, partition = _lines(svg, "wall-load-bearing"), _lines(svg, "wall")
    assert len(bearing) == 1 and len(partition) == 1
    assert float(bearing[0].get("stroke-width", 0)) > float(partition[0].get("stroke-width", 0))


def test_a_vertical_wall_is_drawn_vertically() -> None:
    (line,) = _lines(rendre(_plan(_BEARING)), "wall-load-bearing")
    assert float(line.get("x1", 0)) == float(line.get("x2", 1))
    assert float(line.get("y1", 0)) != float(line.get("y2", 0))


def test_comparison_draws_walls_in_both_panels() -> None:
    svg = comparer(_plan(_BEARING), _plan(_BEARING))
    assert len(_lines(svg, "wall-load-bearing")) == 2
