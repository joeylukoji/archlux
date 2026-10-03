"""Taxonomy of geometric pathologies before BIM export."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Polygon, box

from archlux._deprecation import Alias, lazy_aliases
from archlux.types import Plan, Room, Wall

__all__ = ["PathologyDiagnostic", "diagnose"]

_EPS = 1e-9
_AREA_TOL = 1e-9


@dataclass(frozen=True, slots=True)
class PathologyDiagnostic:
    """List of pathology codes; empty <=> exportable."""

    pathologies: tuple[str, ...]

    @property
    def exportable(self) -> bool:
        """No blocking pathology."""
        return not self.pathologies


def _room_box(room: Room) -> Polygon:
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
    found: list[str] = []
    rooms_ok: list[tuple[Room, Polygon]] = []
    for room in rooms:
        if room.w <= _EPS or room.h <= _EPS:
            found.append(f"dimension_non_positive:{room.id}")
            continue
        poly = _room_box(room)
        if not poly.is_valid:
            found.append(f"auto_intersection:{room.id}")
        rooms_ok.append((room, poly))
    return found, rooms_ok


def _wall_pathologies(walls: tuple[Wall, ...]) -> list[str]:
    """Degenerate (zero-length) walls.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    return [f"arete_nulle:{wall.id}" for wall in walls if _zero_length_edge(wall)]


def _orphan_opening_pathologies(plan: Plan) -> list[str]:
    """Openings on a wall absent from ``plan.walls``.

    IFC4 wants every ``IfcOpeningElement`` to void an element.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    walls = {wall.id for wall in plan.walls}
    return [
        f"ouverture_orpheline:{opening.id}"
        for opening in plan.openings
        if opening.wall_id not in walls
    ]


def _outline_pathologies(outline: tuple[tuple[float, float], ...]) -> list[str]:
    """Duplicate vertices, self-intersection, or a degenerate/open outline.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    if not outline:
        return []
    found: list[str] = []
    if _duplicate_vertices(outline):
        found.append("sommets_dupliques:outline")
    if len(outline) >= 3:
        envelope = Polygon(outline)
        if not envelope.is_valid:
            found.append("auto_intersection:outline")
        elif envelope.area <= _AREA_TOL or not envelope.exterior.is_ring:
            found.append("solide_non_ferme:outline")
    else:
        found.append("solide_non_ferme:outline")
    return found


def _overlap_pathologies(rooms_ok: list[tuple[Room, Polygon]]) -> list[str]:
    """Pairwise room overlap, ``O(n^2)``, accepted.

    Extracted from :func:`diagnose` (PLAN.md phase 4, block 13, item 38).
    """
    found: list[str] = []
    for i, (a, ra) in enumerate(rooms_ok):
        for b, rb in rooms_ok[i + 1 :]:
            if ra.intersection(rb).area > _AREA_TOL:
                pair = "|".join(sorted((a.id, b.id)))
                found.append(f"chevauchement:{pair}")
    return found


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
    found, rooms_ok = _room_pathologies(plan.rooms)
    found += _wall_pathologies(plan.walls)
    found += _orphan_opening_pathologies(plan)
    found += _outline_pathologies(plan.outline)
    found += _overlap_pathologies(rooms_ok)
    return PathologyDiagnostic(pathologies=tuple(found))


def _zero_length_edge(wall: Wall) -> bool:
    """Say whether the wall is degenerate (zero length within ``_EPS``)."""
    return bool(LineString([wall.a, wall.b]).length <= _EPS)


def _duplicate_vertices(outline: tuple[tuple[float, float], ...]) -> bool:
    """Say whether the outline repeats a vertex, within 1e-9 m."""
    seen: set[tuple[float, float]] = set()
    for point in outline:
        key = (round(point[0], 9), round(point[1], 9))
        if key in seen:
            return True
        seen.add(key)
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
