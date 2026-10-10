"""DXF reading: rooms, walls, outline and structure drawn on named layers (PLAN.md 5.1).

The reader needs ``ezdxf`` (extra ``cad``: ``pip install "archlux[cad]"``), imported at
call time so that ``import archlux`` never loads it.

Conventions, all on **model space** entities (block references are not expanded):

- a room is a closed, straight polyline (``LWPOLYLINE`` or 2D ``POLYLINE``) with four
  axis-aligned sides; anything else is refused, never approximated;
- its type is the ``TEXT`` or ``MTEXT`` label placed inside it, on the label layer
  (by default the room layer), lowercased with spaces as ``_`` (``"Living room"`` gives
  ``"living_room"``);
- walls are ``LINE`` entities or polyline segments;
- columns (structure only) are ``POINT`` entities and ``CIRCLE`` centers.

Lengths are converted to metres from the ``$INSUNITS`` header (a unitless drawing is
read as metres; an exotic unit is refused), unless ``scale`` overrides it. Layer names
compare without case, as in every CAD program.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from archlux.errors import InvalidInput, UnsupportedInput
from archlux.io._footprint import DIGITS, rectangle
from archlux.types import Plan, Point, Room, Structure, Wall

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["load_dxf_plan", "load_dxf_structure"]

_POLYLINES = frozenset({"LWPOLYLINE", "POLYLINE"})


_INSUNITS: dict[int, float] = {
    0: 1.0,  # unitless: read as metres
    1: 0.0254,  # inch
    2: 0.3048,  # foot
    4: 0.001,  # millimetre
    5: 0.01,  # centimetre
    6: 1.0,  # metre
    10: 0.9144,  # yard
    14: 0.1,  # decimetre
}
"""Metres per drawing unit, by ``$INSUNITS`` code. Written out rather than taken from
``ezdxf.units``, whose inch is ``0.0254000000001016`` m."""


@dataclass(frozen=True, slots=True)
class _Drawing:
    """Model space entities of a DXF file, and the factor that turns its units into metres."""

    entities: tuple[Any, ...]
    scale: float


def _ezdxf() -> ModuleType:
    """Import ``ezdxf`` or explain how to install it.

    Returns
    -------
    module
        The ``ezdxf`` package.

    Raises
    ------
    UnsupportedInput
        ``ezdxf`` is not installed.
    """
    if importlib.util.find_spec("ezdxf") is None:
        raise UnsupportedInput('reading DXF needs ezdxf: pip install "archlux[cad]"')
    import ezdxf
    import ezdxf.path

    return ezdxf


def _read(path: Path | str, scale: float | None) -> _Drawing:
    """Open a DXF file and resolve its unit.

    Parameters
    ----------
    path
        The ``.dxf`` file, ASCII or binary.
    scale
        Metres per drawing unit; ``None`` takes it from ``$INSUNITS``.

    Returns
    -------
    _Drawing
        The model space entities and the unit factor.

    Raises
    ------
    InvalidInput
        The file cannot be read as DXF, or ``scale`` is not a positive finite number.
    """
    if scale is not None and not 0.0 < scale < float("inf"):
        raise InvalidInput("scale", f"must be a positive finite number, got {scale!r}")
    ezdxf = _ezdxf()
    try:
        doc = ezdxf.readfile(Path(path))
    except (OSError, ezdxf.DXFError) as cause:
        raise InvalidInput("path", f"{path} is not a readable DXF file: {cause}") from cause
    if scale is None:
        scale = _INSUNITS.get(doc.units)
    if scale is None:
        raise InvalidInput(
            "scale",
            f"{path}: unsupported $INSUNITS {doc.units}",
            "pass the metres per drawing unit",
        )
    return _Drawing(tuple(doc.modelspace()), float(scale))


def _on(drawing: _Drawing, layer: str, kinds: frozenset[str]) -> Iterator[Any]:
    """Entities of the given kinds on a layer, compared without case.

    Parameters
    ----------
    drawing
        The read drawing.
    layer
        Layer name.
    kinds
        DXF entity types to keep.

    Yields
    ------
    DXFEntity
        The matching entities, in file order.
    """
    wanted = layer.casefold()
    for entity in drawing.entities:
        if entity.dxftype() in kinds and entity.dxf.layer.casefold() == wanted:
            yield entity


def _metres(drawing: _Drawing, x: float, y: float) -> Point:
    """Convert a drawing point to metres.

    Parameters
    ----------
    drawing
        Gives the unit factor.
    x, y
        Coordinates in drawing units.

    Returns
    -------
    Point
        The point in metres, rounded to the nanometre.
    """
    return (round(x * drawing.scale, DIGITS), round(y * drawing.scale, DIGITS))


def _vertices(
    drawing: _Drawing,
    entity: Any,  # noqa: ANN401 - an ezdxf entity, its kind told by dxftype()
) -> tuple[tuple[Point, ...], bool]:
    """Vertices of a straight polyline, in metres and world coordinates.

    Parameters
    ----------
    drawing
        Gives the unit factor.
    entity
        ``LWPOLYLINE`` or ``POLYLINE``.

    Returns
    -------
    tuple of Point, bool
        The vertices, the closing one not repeated, and whether the polyline is closed.

    Raises
    ------
    UnsupportedInput
        The polyline has an arc segment (bulge), or is a 3D polyline or a mesh.
    """
    where = f"{entity.dxftype()} #{entity.dxf.handle} on layer {entity.dxf.layer!r}"
    if entity.dxftype() == "POLYLINE" and not entity.is_2d_polyline:
        raise UnsupportedInput(f"{where}: only 2D polylines are read")
    path = _ezdxf().path.make_path(entity)
    if path.has_curves:
        raise UnsupportedInput(f"{where}: arc segments (bulges) are not supported")
    points = [_metres(drawing, v.x, v.y) for v in path.control_vertices()]
    closed = bool(entity.closed if entity.dxftype() == "LWPOLYLINE" else entity.is_closed)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
        closed = True
    return tuple(points), closed


def _labels(drawing: _Drawing, layer: str) -> list[tuple[Point, str]]:
    """``TEXT`` and ``MTEXT`` labels of a layer: anchor point in metres, normalized text.

    Parameters
    ----------
    drawing
        The read drawing.
    layer
        Label layer.

    Returns
    -------
    list of (Point, str)
        Anchor and text, ``"Living room"`` normalized to ``"living_room"``.
    """
    labels = []
    for entity in _on(drawing, layer, frozenset({"TEXT", "MTEXT"})):
        text = "_".join(entity.plain_text().split()).casefold()
        if not text:
            continue
        if entity.dxftype() == "TEXT":
            align, insert, other = entity.get_placement()
            anchor = entity.ocs().to_wcs(
                other if other is not None and align.name != "LEFT" else insert
            )
        else:
            anchor = entity.dxf.insert
        labels.append((_metres(drawing, anchor.x, anchor.y), text))
    return labels


def _room_type(
    rect: tuple[float, float, float, float],
    labels: list[tuple[Point, str]],
    default_type: str | None,
    where: str,
) -> str:
    """The type of a room: its single label inside, else ``default_type``.

    Parameters
    ----------
    rect
        ``(x, y, w, h)`` of the room, in metres.
    labels
        Every label of the label layer.
    default_type
        Type of an unlabelled room; ``None`` refuses one.
    where
        Names the entity in the error message.

    Returns
    -------
    str
        The room type.

    Raises
    ------
    InvalidInput
        Two different labels in the room, or none and no ``default_type``.
    """
    x, y, w, h = rect
    inside = {text for (u, v), text in labels if x <= u <= x + w and y <= v <= y + h}
    if len(inside) > 1:
        raise InvalidInput("room_layer", f"{where}: several labels {sorted(inside)}")
    if inside:
        return inside.pop()
    if default_type is None:
        raise InvalidInput(
            "room_layer",
            f"{where}: no TEXT or MTEXT label inside the room",
            "label it with its type, or pass default_type",
        )
    return default_type


def _rooms(
    drawing: _Drawing, layer: str, label_layer: str, default_type: str | None
) -> tuple[Room, ...]:
    """Rooms drawn on a layer, numbered per type in reading order (bottom to top, left to right).

    Parameters
    ----------
    drawing
        The read drawing.
    layer
        Room layer.
    label_layer
        Layer of the type labels.
    default_type
        Type of an unlabelled room, or ``None``.

    Returns
    -------
    tuple of Room
        The rooms, identified ``"<type>-<n>"``.

    Raises
    ------
    InvalidInput
        No polyline on the layer, or an open one.
    """
    labels, typed = _labels(drawing, label_layer), []
    for entity in _on(drawing, layer, _POLYLINES):
        where = f"{entity.dxftype()} #{entity.dxf.handle} on layer {layer!r}"
        points, closed = _vertices(drawing, entity)
        if not closed:
            raise InvalidInput(
                "room_layer", f"{where}: open polyline", "close it, or move it off the layer"
            )
        rect = rectangle(points, where)
        typed.append((rect[1], rect[0], _room_type(rect, labels, default_type, where), rect))
    if not typed:
        raise InvalidInput("room_layer", f"no room polyline on layer {layer!r}")
    count: dict[str, int] = {}
    rooms = []
    for _, _, kind, (x, y, w, h) in sorted(typed):
        count[kind] = count.get(kind, 0) + 1
        rooms.append(Room(id=f"{kind}-{count[kind]}", type=kind, x=x, y=y, w=w, h=h))
    return tuple(rooms)


def _segments(drawing: _Drawing, layer: str) -> list[tuple[Point, Point]]:
    """Straight segments of a layer: ``LINE`` entities and polyline sides.

    Parameters
    ----------
    drawing
        The read drawing.
    layer
        Wall layer.

    Returns
    -------
    list of (Point, Point)
        The segments, in metres, zero-length ones dropped.
    """
    segments = []
    for entity in _on(drawing, layer, _POLYLINES | {"LINE"}):
        if entity.dxftype() == "LINE":
            a, b = entity.dxf.start, entity.dxf.end
            segments.append((_metres(drawing, a.x, a.y), _metres(drawing, b.x, b.y)))
            continue
        points, closed = _vertices(drawing, entity)
        ends = points + points[:1] if closed else points
        segments.extend(pairwise(ends))
    return [(a, b) for a, b in segments if a != b]


def _walls(drawing: _Drawing, layer: str, prefix: str, load_bearing: bool) -> tuple[Wall, ...]:
    """Walls of a layer, identified ``"<prefix>-<n>"`` in file order.

    Parameters
    ----------
    drawing
        The read drawing.
    layer
        Wall layer.
    prefix
        Identifier prefix.
    load_bearing
        Whether the walls are load-bearing.

    Returns
    -------
    tuple of Wall
        The walls.
    """
    return tuple(
        Wall(id=f"{prefix}-{n}", a=a, b=b, load_bearing=load_bearing)
        for n, (a, b) in enumerate(_segments(drawing, layer), start=1)
    )


def _outline(drawing: _Drawing, layer: str | None, rooms: tuple[Room, ...]) -> tuple[Point, ...]:
    """The outline: the single closed polyline of its layer, else the rooms' bounding box.

    Parameters
    ----------
    drawing
        The read drawing.
    layer
        Outline layer, or ``None``.
    rooms
        The rooms read.

    Returns
    -------
    tuple of Point
        The outline vertices, counterclockwise for the bounding box.

    Raises
    ------
    InvalidInput
        The layer does not hold exactly one closed polyline.
    """
    if layer is None:
        x0, y0 = min(r.x for r in rooms), min(r.y for r in rooms)
        x1, y1 = max(r.x + r.w for r in rooms), max(r.y + r.h for r in rooms)
        return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    found = [
        p
        for p, closed in (_vertices(drawing, e) for e in _on(drawing, layer, _POLYLINES))
        if closed
    ]
    if len(found) != 1:
        raise InvalidInput(
            "outline_layer", f"needs exactly one closed polyline on {layer!r}, got {len(found)}"
        )
    return found[0]


def load_dxf_plan(
    path: Path | str,
    room_layer: str = "ROOMS",
    *,
    label_layer: str | None = None,
    wall_layer: str | None = None,
    load_bearing_layer: str | None = None,
    outline_layer: str | None = None,
    default_type: str | None = None,
    scale: float | None = None,
) -> Plan:
    """Read a plan from a DXF drawing.

    Parameters
    ----------
    path : Path or str
        The ``.dxf`` file.
    room_layer : str, optional
        Layer of the room rectangles.
    label_layer : str, optional
        Layer of the type labels; defaults to ``room_layer``.
    wall_layer : str, optional
        Layer of the partitions, read as non-load-bearing walls ``"wall-<n>"``.
    load_bearing_layer : str, optional
        Layer of the load-bearing walls, read as ``"load-bearing-<n>"``.
    outline_layer : str, optional
        Layer of the single closed outline; defaults to the rooms' bounding box.
    default_type : str, optional
        Type of an unlabelled room; by default an unlabelled room is refused.
    scale : float, optional
        Metres per drawing unit, overriding ``$INSUNITS`` (``0.001`` for millimetres).

    Returns
    -------
    Plan
        The proposed plan, rooms identified ``"<type>-<n>"``.

    Raises
    ------
    InvalidInput
        Unreadable file, no room, ambiguous or missing label, bad outline or scale.
    UnsupportedInput
        ``ezdxf`` missing, or a room that is not an axis-aligned rectangle.
    """
    drawing = _read(path, scale)
    rooms = _rooms(drawing, room_layer, label_layer or room_layer, default_type)
    walls = _walls(drawing, wall_layer, "wall", False) if wall_layer else ()
    if load_bearing_layer:
        walls += _walls(drawing, load_bearing_layer, "load-bearing", True)
    return Plan(rooms=rooms, walls=walls, outline=_outline(drawing, outline_layer, rooms))


def load_dxf_structure(
    path: Path | str, layer: str = "LOAD_BEARING", *, scale: float | None = None
) -> Structure:
    """Read the load-bearing structure from a DXF drawing.

    Parameters
    ----------
    path : Path or str
        The ``.dxf`` file.
    layer : str, optional
        Layer of the load-bearing walls (``LINE``, polylines) and columns (``POINT``,
        ``CIRCLE`` centers).
    scale : float, optional
        Metres per drawing unit, overriding ``$INSUNITS``.

    Returns
    -------
    Structure
        Walls ``"load-bearing-<n>"`` in file order, and columns.

    Raises
    ------
    InvalidInput
        Unreadable file, or nothing on the layer.
    UnsupportedInput
        ``ezdxf`` missing, or a polyline with arc segments.
    """
    drawing = _read(path, scale)
    walls = _walls(drawing, layer, "load-bearing", True)
    columns = tuple(
        _metres(drawing, p.x, p.y)
        for p in (
            e.dxf.location if e.dxftype() == "POINT" else e.ocs().to_wcs(e.dxf.center)
            for e in _on(drawing, layer, frozenset({"POINT", "CIRCLE"}))
        )
    )
    if not walls and not columns:
        raise InvalidInput("layer", f"no wall or column on layer {layer!r}")
    return Structure(load_bearing_walls=walls, columns=columns)
