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


def diagnose(plan: Plan) -> PathologyDiagnostic:
    """List the pathologies that break an IFC/DXF export.

    Codes
    -----
    ``arete_nulle``, ``sommets_dupliques``, ``auto_intersection``,
    ``solide_non_ferme``, ``overlap``, ``dimension_non_positive``,
    ``ouverture_orpheline`` (an opening on a wall absent from ``plan.walls``: IFC4 wants
    every ``IfcOpeningElement`` to void an element).
    """
    trouves: list[str] = []
    # Rooms with non-positive dimensions: do not geometrize them (``box`` normalizes
    # the bounds and would invent overlaps / self-intersections).
    # The polygons are built **once**: the overlap loop is quadratic, and rebuilding
    # a ``box`` on every comparison would have been too.
    pieces_ok: list[tuple[Room, Polygon]] = []

    for room in plan.rooms:
        if room.w <= _EPS or room.h <= _EPS:
            trouves.append(f"dimension_non_positive:{room.id}")
            continue
        poly = _piece_box(room)
        if not poly.is_valid:
            trouves.append(f"auto_intersection:{room.id}")
        pieces_ok.append((room, poly))

    for wall in plan.walls:
        if _arete_nulle(wall):
            trouves.append(f"arete_nulle:{wall.id}")

    walls = {wall.id for wall in plan.walls}
    trouves.extend(
        f"ouverture_orpheline:{ouv.id}" for ouv in plan.openings if ouv.wall_id not in walls
    )

    if plan.outline:
        if _sommets_dupliques(plan.outline):
            trouves.append("sommets_dupliques:outline")
        if len(plan.outline) >= 3:
            enveloppe = Polygon(plan.outline)
            if not enveloppe.is_valid:
                trouves.append("auto_intersection:outline")
            elif enveloppe.area <= _TOL_AIRE or not enveloppe.exterior.is_ring:
                trouves.append("solide_non_ferme:outline")
        else:
            trouves.append("solide_non_ferme:outline")

    for i, (a, ra) in enumerate(pieces_ok):
        for b, rb in pieces_ok[i + 1 :]:
            if ra.intersection(rb).area > _TOL_AIRE:
                paire = "|".join(sorted((a.id, b.id)))
                trouves.append(f"chevauchement:{paire}")

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
        "diagnostiquer": Alias(diagnose, "archlux.export.pathologie.diagnose"),
        "DiagnosticPathologie": Alias(
            PathologyDiagnostic, "archlux.export.pathologie.PathologyDiagnostic"
        ),
    },
)
