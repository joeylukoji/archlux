"""Taxonomie des pathologies géométriques avant export BIM."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Polygon, box

from archlux.types import Mur, Piece, Plan

__all__ = ["DiagnosticPathologie", "diagnostiquer"]

_EPS = 1e-9
_TOL_AIRE = 1e-9


@dataclass(frozen=True, slots=True)
class DiagnosticPathologie:
    """Liste de codes de pathologie ; vide ⇔ exportable."""

    pathologies: tuple[str, ...]

    @property
    def exportable(self) -> bool:
        """Aucune pathologie bloquante."""
        return not self.pathologies


def _piece_box(piece: Piece) -> Polygon:
    """Rectangle Shapely d'une piece, en coordonnees absolues."""
    return box(piece.x, piece.y, piece.x + piece.w, piece.y + piece.h)


def diagnostiquer(plan: Plan) -> DiagnosticPathologie:
    """Recenser les pathologies qui cassent un export IFC/DXF.

    Codes
    -----
    ``arete_nulle``, ``sommets_dupliques``, ``auto_intersection``,
    ``solide_non_ferme``, ``chevauchement``, ``dimension_non_positive``.
    """
    trouves: list[str] = []
    # Pièces à cotes non positives : ne pas les géométriser (``box`` normalise les
    # bornes et inventerait des chevauchements / auto-intersections).
    # Les polygones sont construits **une fois** : la boucle de chevauchement est
    # quadratique, et reconstruire un ``box`` par comparaison l'était aussi.
    pieces_ok: list[tuple[Piece, Polygon]] = []

    for piece in plan.pieces:
        if piece.w <= _EPS or piece.h <= _EPS:
            trouves.append(f"dimension_non_positive:{piece.id}")
            continue
        poly = _piece_box(piece)
        if not poly.is_valid:
            trouves.append(f"auto_intersection:{piece.id}")
        pieces_ok.append((piece, poly))

    for mur in plan.murs:
        if _arete_nulle(mur):
            trouves.append(f"arete_nulle:{mur.id}")

    if plan.contour:
        if _sommets_dupliques(plan.contour):
            trouves.append("sommets_dupliques:contour")
        if len(plan.contour) >= 3:
            enveloppe = Polygon(plan.contour)
            if not enveloppe.is_valid:
                trouves.append("auto_intersection:contour")
            elif enveloppe.area <= _TOL_AIRE or not enveloppe.exterior.is_ring:
                trouves.append("solide_non_ferme:contour")
        else:
            trouves.append("solide_non_ferme:contour")

    for i, (a, ra) in enumerate(pieces_ok):
        for b, rb in pieces_ok[i + 1 :]:
            if ra.intersection(rb).area > _TOL_AIRE:
                paire = "|".join(sorted((a.id, b.id)))
                trouves.append(f"chevauchement:{paire}")

    return DiagnosticPathologie(pathologies=tuple(trouves))


def _arete_nulle(mur: Mur) -> bool:
    """Dire si le mur est degenere (longueur nulle a ``_EPS`` pres)."""
    return bool(LineString([mur.a, mur.b]).length <= _EPS)


def _sommets_dupliques(contour: tuple[tuple[float, float], ...]) -> bool:
    """Dire si le contour repete un sommet, a 1e-9 m pres."""
    vus: set[tuple[float, float]] = set()
    for point in contour:
        cle = (round(point[0], 9), round(point[1], 9))
        if cle in vus:
            return True
        vus.add(cle)
    return False
