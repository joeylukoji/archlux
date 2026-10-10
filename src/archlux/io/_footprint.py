"""Footprints shared by the DXF and IFC readers: a room must be an axis-aligned rectangle."""

from __future__ import annotations

from archlux.errors import UnsupportedInput
from archlux.tolerances import SNAP_M
from archlux.types import Point

__all__ = ["DIGITS", "rectangle"]

DIGITS = 9
"""Converted coordinates are rounded to the nanometre: ``3500 mm * 0.001`` gives
``3.5000000000000004``, a noise no drawing carries."""


def rectangle(points: tuple[Point, ...], where: str) -> tuple[float, float, float, float]:
    """The axis-aligned rectangle the vertices describe.

    Parameters
    ----------
    points
        Vertices of a closed polyline, the closing one not repeated.
    where
        Names the entity in the error message.

    Returns
    -------
    tuple of float
        ``(x, y, w, h)``, bottom-left corner first.

    Raises
    ------
    UnsupportedInput
        The polyline is not four axis-aligned sides of positive length.
    """
    if len(points) != 4:
        raise UnsupportedInput(f"{where}: a room needs 4 vertices, got {len(points)}")
    x0, x1 = min(x for x, _ in points), max(x for x, _ in points)
    y0, y1 = min(y for _, y in points), max(y for _, y in points)
    corners = [(_snap(x, x0, x1), _snap(y, y0, y1)) for x, y in points]
    if not _closes_a_rectangle(corners) or min(x1 - x0, y1 - y0) <= SNAP_M:
        raise UnsupportedInput(f"{where}: a room must be an axis-aligned rectangle")
    return x0, y0, x1 - x0, y1 - y0


def _closes_a_rectangle(corners: list[tuple[float | None, float | None]]) -> bool:
    """Whether four snapped vertices are four distinct corners joined by axis-aligned sides.

    Parameters
    ----------
    corners
        The vertices snapped by :func:`_snap`, in polyline order.

    Returns
    -------
    bool
        ``True`` for a rectangle; a bowtie visits the four corners but crosses itself.
    """
    if len(set(corners)) != 4 or any(None in corner for corner in corners):
        return False
    sides = zip(corners, corners[1:] + corners[:1], strict=True)
    return all(a[0] == b[0] or a[1] == b[1] for a, b in sides)


def _snap(value: float, low: float, high: float) -> float | None:
    """The end of ``[low, high]`` within ``SNAP_M`` of ``value``.

    Parameters
    ----------
    value
        A coordinate.
    low, high
        The extreme coordinates on that axis.

    Returns
    -------
    float or None
        ``low`` or ``high`` when close enough, else ``None``: the vertex is not a corner.
    """
    for end in (low, high):
        if abs(value - end) <= SNAP_M:
            return end
    return None
