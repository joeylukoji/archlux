"""Minimal DXF writing (ASCII), without external dependency."""

from __future__ import annotations

from pathlib import Path

from archlux._deprecation import renamed_parameters
from archlux.errors import InvariantViolation
from archlux.export.pathologies import diagnose
from archlux.types import Plan

__all__ = ["to_dxf"]


@renamed_parameters({"chemin": "path"})
def to_dxf(plan: Plan, path: Path | str) -> None:
    """Export the rooms as ``LWPOLYLINE`` (2D plan).

    Parameters
    ----------
    plan : Plan
        Plan to export.
    path : Path or str
        ``.dxf`` file (overwritten).

    Raises
    ------
    InvariantViolation
        Blocking geometric pathology.
    """
    path = Path(path)
    diag = diagnose(plan)
    if not diag.exportable:
        raise InvariantViolation(diag.pathologies)

    rows: list[str] = [
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
    for piece in plan.rooms:
        x0, y0, x1, y1 = piece.x, piece.y, piece.x + piece.w, piece.y + piece.h
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        rows.extend(
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
        for x, y in corners:
            rows.extend(["10", f"{x:.6f}", "20", f"{y:.6f}"])
    for wall in plan.walls:
        rows.extend(
            [
                "0",
                "LINE",
                "8",
                wall.id,
                "10",
                f"{wall.a[0]:.6f}",
                "20",
                f"{wall.a[1]:.6f}",
                "11",
                f"{wall.b[0]:.6f}",
                "21",
                f"{wall.b[1]:.6f}",
            ]
        )
    rows.extend(["0", "ENDSEC", "0", "EOF"])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
