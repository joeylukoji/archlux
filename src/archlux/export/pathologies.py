"""Taxonomy of geometric pathologies before BIM export."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Polygon, box

from archlux._deprecation import Alias, lazy_aliases
from archlux.types import Plan, Room, Wall

__all__ = ["PathologyDiagnostic", "diagnose"]

_EPS = 1e-9
_TOL_AIRE = 1e-9


@dataclass(frozen=True, slots=True)
class PathologyDiagnostic:
    """List of pathology codes; empty <=> exportable."""

    pathologies: tuple[str, ...]

    @property
    def exportable(self) -> bool:
        """No blocking pathology."""
        return not self.pathologies


def _piece_box(room: Room) -> Polygon:
    """Shapely rectangle of a room, in absolute coordinates."""
    return box(room.x, room.y, room.x + room.w, room.y + room.h)


def _room_pathologies(rooms: tuple[Room, ...]) -> tuple[list[str], list[tuple[Room, Polygon]]]:
    """Non-positive dimensions and self-intersections, plus the valid rooms as polygons.

    Rooms with non-positive dimensions are not geometrized (``box`` normalizes the
    bounds and would invent overlaps / self-intersections). The polygons are returned
    for :func:`_overlap_pathologies` to reuse: the overlap check is quadratic, and
    rebuilding a ``box`` on every comparison would have been too.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    trouves: list[str] = []
    pieces_ok: list[tuple[Room, Polygon]] = []
    for room in rooms:
        if room.w <= _EPS or room.h <= _EPS:
            trouves.append(f"dimension_non_positive:{room.id}")
            continue
        poly = _piece_box(room)
        if not poly.is_valid:
            trouves.append(f"auto_intersection:{room.id}")
        pieces_ok.append((room, poly))
    return trouves, pieces_ok


def _wall_pathologies(walls: tuple[Wall, ...]) -> list[str]:
    """Degenerate (zero-length) walls.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    return [f"arete_nulle:{wall.id}" for wall in walls if _arete_nulle(wall)]


def _orphan_opening_pathologies(plan: Plan) -> list[str]:
    """Openings on a wall absent from ``plan.walls``.

    IFC4 wants every ``IfcOpeningElement`` to void an element.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    walls = {wall.id for wall in plan.walls}
    return [f"ouverture_orpheline:{ouv.id}" for ouv in plan.openings if ouv.wall_id not in walls]


def _outline_pathologies(outline: tuple[tuple[float, float], ...]) -> list[str]:
    """Duplicate vertices, self-intersection, or a degenerate/open outline.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    if not outline:
        return []
    trouves: list[str] = []
    if _sommets_dupliques(outline):
        trouves.append("sommets_dupliques:outline")
    if len(outline) >= 3:
        enveloppe = Polygon(outline)
        if not enveloppe.is_valid:
            trouves.append("auto_intersection:outline")
        elif enveloppe.area <= _TOL_AIRE or not enveloppe.exterior.is_ring:
            trouves.append("solide_non_ferme:outline")
    else:
        trouves.append("solide_non_ferme:outline")
    return trouves


def _overlap_pathologies(pieces_ok: list[tuple[Room, Polygon]]) -> list[str]:
    """Pairwise room overlap, ``O(n^2)``, accepted.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    trouves: list[str] = []
    for i, (a, ra) in enumerate(pieces_ok):
        for b, rb in pieces_ok[i + 1 :]:
            if ra.intersection(rb).area > _TOL_AIRE:
                paire = "|".join(sorted((a.id, b.id)))
                trouves.append(f"chevauchement:{paire}")
    return trouves


def diagnose(plan: Plan) -> PathologyDiagnostic:
    """List the pathologies that break an IFC/DXF export.

    Codes
    -----
    Each pathology is ``code:subject``:

    - ``dimension_non_positive:{room}``, ``auto_intersection:{room}``;
    - ``arete_nulle:{wall}`` (zero-length wall);
    - ``ouverture_orpheline:{opening}`` (an opening on a wall absent from
      ``plan.walls``: IFC4 wants every ``IfcOpeningElement`` to void an element);
    - ``sommets_dupliques:outline``, ``auto_intersection:outline``,
      ``solide_non_ferme:outline``;
    - ``chevauchement:{a}|{b}`` (two rooms overlap; ids sorted).
    """
    trouves, pieces_ok = _room_pathologies(plan.rooms)
    trouves += _wall_pathologies(plan.walls)
    trouves += _orphan_opening_pathologies(plan)
    trouves += _outline_pathologies(plan.outline)
    trouves += _overlap_pathologies(pieces_ok)
    return PathologyDiagnostic(pathologies=tuple(trouves))


def _arete_nulle(wall: Wall) -> bool:
    """Say whether the wall is degenerate (zero length within ``_EPS``)."""
    return bool(LineString([wall.a, wall.b]).length <= _EPS)


def _sommets_dupliques(outline: tuple[tuple[float, float], ...]) -> bool:
    """Say whether the outline repeats a vertex, within 1e-9 m."""
    vus: set[tuple[float, float]] = set()
    for point in outline:
        cle = (round(point[0], 9), round(point[1], 9))
        if cle in vus:
            return True
        vus.add(cle)
    return False


__getattr__ = lazy_aliases(
    __name__,
    {
        "diagnostiquer": Alias(diagnose, "archlux.export.pathologies.diagnose"),
        "DiagnosticPathologie": Alias(
            PathologyDiagnostic, "archlux.export.pathologies.PathologyDiagnostic"
        ),
    },
)
