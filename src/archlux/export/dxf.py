"""Écriture DXF minimale (ASCII), sans dépendance externe."""

from __future__ import annotations

from pathlib import Path

from archlux.erreurs import InvariantViole
from archlux.export.pathologie import diagnostiquer
from archlux.types import Plan

__all__ = ["to_dxf"]


def to_dxf(plan: Plan, chemin: Path) -> None:
    """Exporter les pièces comme ``LWPOLYLINE`` (plan 2D).

    Parameters
    ----------
    plan : Plan
        Plan à exporter.
    chemin : Path
        Fichier ``.dxf`` (écrasé).

    Raises
    ------
    InvariantViole
        Pathologie géométrique bloquante.
    """
    diag = diagnostiquer(plan)
    if not diag.exportable:
        raise InvariantViole(diag.pathologies)

    lignes: list[str] = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for piece in plan.pieces:
        x0, y0, x1, y1 = piece.x, piece.y, piece.x + piece.w, piece.y + piece.h
        coins = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        lignes.extend(
            [
                "0",
                "LWPOLYLINE",
                "8",
                piece.id,
                "90",
                "4",
                "70",
                "1",
            ]
        )
        for x, y in coins:
            lignes.extend(["10", f"{x:.6f}", "20", f"{y:.6f}"])
    for mur in plan.murs:
        lignes.extend(
            [
                "0",
                "LINE",
                "8",
                mur.id,
                "10",
                f"{mur.a[0]:.6f}",
                "20",
                f"{mur.a[1]:.6f}",
                "11",
                f"{mur.b[0]:.6f}",
                "21",
                f"{mur.b[1]:.6f}",
            ]
        )
    lignes.extend(["0", "ENDSEC", "0", "EOF"])
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
