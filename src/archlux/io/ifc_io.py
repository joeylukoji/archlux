"""IFC reading: rooms from ``IfcSpace``, walls from ``IfcWall``, columns (PLAN.md 5.1, optional).

The reader needs ``ifcopenshell`` (extra ``bim``: ``pip install "archlux[bim]"``),
imported at call time. It reads the model without a geometry kernel, so only footprints
it can compute exactly are accepted:

- a room is an ``IfcSpace`` whose ``FootPrint`` polyline, or whose ``Body`` vertical
  extrusion of a rectangle or of a straight closed profile, is an axis-aligned rectangle
  once placed; anything else is refused, never approximated;
- its type is its ``LongName``, else its ``ObjectType`` (``"Living room"`` gives
  ``"living_room"``); its identifier is its ``Name`` when every space has a distinct one,
  else ``"<type>-<n>"``;
- a wall is an ``IfcWall`` with an ``Axis`` polyline; it is load-bearing when
  ``Pset_WallCommon.LoadBearing`` is true. A partition without an axis is skipped, a
  load-bearing wall without one is refused;
- a column is the placement origin of an ``IfcColumn``.

Lengths are converted to metres from the project's length unit. A model with spaces on
several storeys needs ``storey``: the plan is one floor.
"""

from __future__ import annotations

import importlib.util
from itertools import pairwise
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from archlux.errors import InvalidInput, UnsupportedInput
from archlux.io._footprint import DIGITS, rectangle
from archlux.types import Plan, Point, Room, Structure, Wall

__all__ = ["load_ifc_plan", "load_ifc_structure"]

_VERTICAL = 1e-9
"""An extrusion is vertical when its direction's horizontal components are below this."""


def _ifcopenshell() -> ModuleType:
    """Import ``ifcopenshell`` and its utilities, or explain how to install it.

    Returns
    -------
    module
        The ``ifcopenshell`` package.

    Raises
    ------
    UnsupportedInput
        ``ifcopenshell`` is not installed.
    """
    if importlib.util.find_spec("ifcopenshell") is None:
        raise UnsupportedInput('reading IFC needs ifcopenshell: pip install "archlux[bim]"')
    import ifcopenshell
    import ifcopenshell.util.element
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit

    return ifcopenshell


def _open(path: Path | str) -> Any:  # noqa: ANN401 - an ifcopenshell model, no stubs
    """Open an IFC file.

    Parameters
    ----------
    path
        The ``.ifc`` file.

    Returns
    -------
    ifcopenshell.file
        The model.

    Raises
    ------
    InvalidInput
        The file cannot be read as IFC.
    """
    ifc = _ifcopenshell()
    try:
        return ifc.open(str(Path(path)))
    except (OSError, RuntimeError, ValueError, ifc.Error) as cause:
        raise InvalidInput("path", f"{path} is not a readable IFC file: {cause}") from cause


def _where(entity: Any) -> str:  # noqa: ANN401 - an ifcopenshell entity
    """``"IfcSpace #12 'bedroom-1'"``, to name an entity in a message.

    Parameters
    ----------
    entity
        An IFC entity.

    Returns
    -------
    str
        Its class, step number and name.
    """
    return f"{entity.is_a()} #{entity.id()} {getattr(entity, 'Name', None)!r}"


def _place(matrix: np.ndarray, points: list[tuple[float, ...]], scale: float) -> tuple[Point, ...]:
    """Local points to world metres, through a 4x4 placement matrix.

    Parameters
    ----------
    matrix
        Homogeneous placement, in model units.
    points
        Local 2D or 3D points, in model units.
    scale
        Metres per model unit.

    Returns
    -------
    tuple of Point
        The placed points, in metres, rounded to the nanometre; a closing point equal to
        the first is dropped.
    """
    placed = []
    for point in points:
        x, y = point[0], point[1]
        z = point[2] if len(point) > 2 else 0.0
        u = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3]
        v = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3]
        placed.append((round(float(u) * scale, DIGITS), round(float(v) * scale, DIGITS)))
    if len(placed) > 1 and placed[0] == placed[-1]:
        placed.pop()
    return tuple(placed)


def _curve_points(curve: Any) -> list[tuple[float, ...]] | None:  # noqa: ANN401
    """Vertices of a straight curve: ``IfcPolyline``, or ``IfcIndexedPolyCurve`` without arcs.

    Parameters
    ----------
    curve
        An IFC curve.

    Returns
    -------
    list of tuple or None
        The vertices in the curve's frame, or ``None`` for any other curve.
    """
    if curve.is_a("IfcPolyline"):
        return [tuple(p.Coordinates) for p in curve.Points]
    if curve.is_a("IfcIndexedPolyCurve"):
        segments = curve.Segments or ()
        if any(not segment.is_a("IfcLineIndex") for segment in segments):
            return None
        return [tuple(p) for p in curve.Points.CoordList]
    return None


def _profile_points(profile: Any) -> list[tuple[float, ...]] | None:  # noqa: ANN401
    """Vertices of a rectangle or straight closed profile, in the solid's frame.

    Parameters
    ----------
    profile
        The swept area of an extrusion.

    Returns
    -------
    list of tuple or None
        The vertices, or ``None`` for a profile that is neither.
    """
    if profile.is_a("IfcRectangleProfileDef"):
        hx, hy = profile.XDim / 2.0, profile.YDim / 2.0
        corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    elif profile.is_a("IfcArbitraryClosedProfileDef") and not profile.is_a(
        "IfcArbitraryProfileDefWithVoids"
    ):
        found = _curve_points(profile.OuterCurve)
        if found is None:
            return None
        corners = [(p[0], p[1]) for p in found]
    else:
        return None
    position = getattr(profile, "Position", None)
    if position is None:
        return [(x, y) for x, y in corners]
    ox, oy = position.Location.Coordinates[:2]
    ux, uy = position.RefDirection.DirectionRatios[:2] if position.RefDirection else (1.0, 0.0)
    norm = (ux * ux + uy * uy) ** 0.5
    ux, uy = ux / norm, uy / norm
    return [(ox + ux * x - uy * y, oy + uy * x + ux * y) for x, y in corners]


def _footprint(space: Any, scale: float) -> tuple[Point, ...]:  # noqa: ANN401
    """World footprint of a space, from its ``FootPrint`` curve or its ``Body`` extrusion.

    Parameters
    ----------
    space
        An ``IfcSpace``.
    scale
        Metres per model unit.

    Returns
    -------
    tuple of Point
        The footprint vertices, in metres.

    Raises
    ------
    UnsupportedInput
        No footprint computable without a geometry kernel.
    """
    placement = _ifcopenshell().util.placement
    matrix = placement.get_local_placement(space.ObjectPlacement)
    for rep in _representations(space):
        for item in rep.Items:
            points = _item_points(item, rep.RepresentationIdentifier, placement)
            if points is not None:
                local, solid = points
                return _place(matrix @ solid, local, scale)
    raise UnsupportedInput(
        f"{_where(space)}: no footprint readable without a geometry kernel "
        "(a FootPrint polyline, or a vertical extrusion of a straight profile)"
    )


def _representations(product: Any) -> list[Any]:  # noqa: ANN401
    """The shape representations of a product, ``FootPrint`` and ``Axis`` first.

    Parameters
    ----------
    product
        An IFC product.

    Returns
    -------
    list
        Its representations, plan ones before ``Body``.
    """
    shape = product.Representation
    if shape is None:
        return []
    order = {"FootPrint": 0, "Axis": 0, "Body": 1}
    return sorted(shape.Representations, key=lambda r: order.get(r.RepresentationIdentifier, 2))


def _item_points(
    item: Any,  # noqa: ANN401 - an ifcopenshell representation item
    identifier: str | None,
    placement: ModuleType,
) -> tuple[list[tuple[float, ...]], np.ndarray] | None:
    """Local vertices of one representation item, and the frame of the item.

    Parameters
    ----------
    item
        A representation item.
    identifier
        Identifier of its representation (``"FootPrint"``, ``"Body"``...).
    placement
        ``ifcopenshell.util.placement``.

    Returns
    -------
    tuple or None
        ``(vertices, 4x4 frame)``, or ``None`` for an item that gives no exact footprint.
    """
    if identifier == "FootPrint":
        found = _curve_points(item)
        return None if found is None else (found, np.eye(4))
    if identifier == "Body" and item.is_a("IfcExtrudedAreaSolid"):
        solid = placement.get_axis2placement(item.Position) if item.Position else np.eye(4)
        world = solid @ np.array([*item.ExtrudedDirection.DirectionRatios, 0.0])
        if abs(world[0]) > _VERTICAL or abs(world[1]) > _VERTICAL:
            return None
        found = _profile_points(item.SweptArea)
        return None if found is None else (found, solid)
    return None


def _storey_of(element: Any) -> Any:  # noqa: ANN401
    """The ``IfcBuildingStorey`` an element belongs to, through aggregation or containment.

    Parameters
    ----------
    element
        An IFC element or space.

    Returns
    -------
    entity or None
        Its storey, or ``None``.
    """
    util = _ifcopenshell().util.element
    seen = 0
    while element is not None and seen < 16:
        if element.is_a("IfcBuildingStorey"):
            return element
        element = util.get_aggregate(element) or util.get_container(element)
        seen += 1
    return None


def _wanted_storey(model: Any, storey: str | None) -> str | None:  # noqa: ANN401
    """The storey to read: the named one, or the only one holding spaces.

    Parameters
    ----------
    model
        The IFC model.
    storey
        Storey ``Name``, or ``None``.

    Returns
    -------
    str or None
        The storey name, or ``None`` for a model without spaces.

    Raises
    ------
    InvalidInput
        Spaces on several storeys and no ``storey``, or no space on the named one.
    """
    names = sorted({_storey_name(space) for space in model.by_type("IfcSpace")})
    if storey is None and len(names) > 1:
        raise InvalidInput("storey", f"spaces on several storeys: {names}", "pass storey=")
    if storey is not None and storey not in names:
        raise InvalidInput("storey", f"no space on storey {storey!r}; storeys: {names}")
    return storey if storey is not None else (names[0] if names else None)


def _on_storey(model: Any, kind: str, storey: str | None) -> list[Any]:  # noqa: ANN401
    """Elements of a kind on the storey to read (see :func:`_wanted_storey`).

    Parameters
    ----------
    model
        The IFC model.
    kind
        IFC class, subclasses included.
    storey
        Storey ``Name``, or ``None``.

    Returns
    -------
    list
        The elements, in step order.
    """
    wanted = _wanted_storey(model, storey)
    elements = sorted(model.by_type(kind), key=lambda e: e.id())
    return [e for e in elements if wanted is None or _storey_name(e) == wanted]


def _storey_name(element: Any) -> str:  # noqa: ANN401
    """Name of an element's storey, ``""`` when it has none.

    Parameters
    ----------
    element
        An IFC element or space.

    Returns
    -------
    str
        The storey ``Name``.
    """
    found = _storey_of(element)
    return "" if found is None else str(found.Name or "")


def _label(space: Any) -> str:  # noqa: ANN401
    """The normalized type label of a space: ``LongName``, else ``ObjectType``.

    Parameters
    ----------
    space
        An ``IfcSpace``.

    Returns
    -------
    str
        ``"Living room"`` as ``"living_room"``; empty when it has neither.
    """
    text = space.LongName or space.ObjectType or ""
    return "_".join(str(text).split()).casefold()


def _rooms(spaces: list[Any], scale: float, default_type: str | None) -> tuple[Room, ...]:
    """Rooms of the spaces, named by ``Name`` when unique, else ``"<type>-<n>"``.

    Parameters
    ----------
    spaces
        The ``IfcSpace`` entities of the storey.
    scale
        Metres per model unit.
    default_type
        Type of an unlabelled space, or ``None``.

    Returns
    -------
    tuple of Room
        The rooms, bottom to top then left to right.

    Raises
    ------
    InvalidInput
        No space, or an unlabelled one without ``default_type``.
    """
    if not spaces:
        raise InvalidInput("path", "no IfcSpace to read")
    typed = []
    for space in spaces:
        kind = _label(space) or default_type
        if kind is None:
            raise InvalidInput(
                "default_type", f"{_where(space)}: no LongName or ObjectType", "pass default_type"
            )
        x, y, w, h = rectangle(_footprint(space, scale), _where(space))
        typed.append((y, x, kind, str(space.Name or ""), (x, y, w, h)))
    typed.sort()
    names = [name for *_, name, _ in typed]
    named = all(names) and len(set(names)) == len(names)
    count: dict[str, int] = {}
    rooms = []
    for _, _, kind, name, (x, y, w, h) in typed:
        count[kind] = count.get(kind, 0) + 1
        room_id = name if named else f"{kind}-{count[kind]}"
        rooms.append(Room(id=room_id, type=kind, x=x, y=y, w=w, h=h))
    return tuple(rooms)


def _load_bearing(wall: Any) -> bool:  # noqa: ANN401
    """``Pset_WallCommon.LoadBearing``, false when absent.

    Parameters
    ----------
    wall
        An ``IfcWall``.

    Returns
    -------
    bool
        Whether the wall is load-bearing.
    """
    psets = _ifcopenshell().util.element.get_psets(wall)
    return bool(psets.get("Pset_WallCommon", {}).get("LoadBearing", False))


def _axis(wall: Any, scale: float) -> tuple[Point, ...] | None:  # noqa: ANN401
    """World vertices of a wall's ``Axis`` polyline.

    Parameters
    ----------
    wall
        An ``IfcWall``.
    scale
        Metres per model unit.

    Returns
    -------
    tuple of Point or None
        The axis vertices in metres, or ``None`` when the wall has no straight axis.
    """
    matrix = _ifcopenshell().util.placement.get_local_placement(wall.ObjectPlacement)
    for rep in _representations(wall):
        if rep.RepresentationIdentifier != "Axis":
            continue
        for item in rep.Items:
            found = _curve_points(item)
            if found is not None:
                return _place(matrix, found, scale)
    return None


_Segment = tuple[str, int, bool, Point, Point]
"""Wall ``Name``, segment rank along its axis, load-bearing, end points."""


def _segments(walls: list[Any], scale: float, only_load_bearing: bool) -> list[_Segment]:
    """Axis segments of the walls, in step order.

    Parameters
    ----------
    walls
        The ``IfcWall`` entities of the storey.
    scale
        Metres per model unit.
    only_load_bearing
        Keep the load-bearing walls only.

    Returns
    -------
    list of _Segment
        One per straight segment of positive length.

    Raises
    ------
    UnsupportedInput
        A load-bearing wall without a straight axis.
    """
    found: list[_Segment] = []
    for wall in walls:
        bearing = _load_bearing(wall)
        if only_load_bearing and not bearing:
            continue
        name = str(wall.Name or "")
        found += [(name, k, bearing, a, b) for k, (a, b) in enumerate(_pairs(wall, scale, bearing))]
    return found


def _pairs(wall: Any, scale: float, bearing: bool) -> list[tuple[Point, Point]]:  # noqa: ANN401
    """Segments of a wall's axis; none for a partition without one.

    Parameters
    ----------
    wall
        An ``IfcWall``.
    scale
        Metres per model unit.
    bearing
        Whether the wall is load-bearing.

    Returns
    -------
    list of (Point, Point)
        The segments of positive length.

    Raises
    ------
    UnsupportedInput
        A load-bearing wall without a straight axis.
    """
    axis = _axis(wall, scale)
    if axis is None and bearing:
        raise UnsupportedInput(f"{_where(wall)}: load-bearing wall without an Axis polyline")
    return [(a, b) for a, b in pairwise(axis or ()) if a != b]


def _walls(walls: list[Any], scale: float, only_load_bearing: bool) -> tuple[Wall, ...]:
    """Walls of the storey, one per axis segment.

    Parameters
    ----------
    walls
        The ``IfcWall`` entities of the storey.
    scale
        Metres per model unit.
    only_load_bearing
        Keep the load-bearing walls only.

    Returns
    -------
    tuple of Wall
        ``Name`` (suffixed ``/<k>`` for a multi-segment axis) when unique, else
        ``"wall-<n>"`` / ``"load-bearing-<n>"``.

    Raises
    ------
    UnsupportedInput
        A load-bearing wall without a straight axis.
    """
    found = _segments(walls, scale, only_load_bearing)
    names = [f"{name}/{k}" if k else name for name, k, *_ in found]
    named = all(name for name, *_ in found) and len(set(names)) == len(names)
    return tuple(
        Wall(
            id=name if named else f"{'load-bearing' if bearing else 'wall'}-{n}",
            a=a,
            b=b,
            load_bearing=bearing,
        )
        for n, ((_, _, bearing, a, b), name) in enumerate(zip(found, names, strict=True), start=1)
    )


def load_ifc_plan(
    path: Path | str, *, storey: str | None = None, default_type: str | None = None
) -> Plan:
    """Read one floor of an IFC model as a plan.

    Parameters
    ----------
    path : Path or str
        The ``.ifc`` file.
    storey : str, optional
        ``Name`` of the storey to read; needed when spaces sit on several.
    default_type : str, optional
        Type of a space with neither ``LongName`` nor ``ObjectType``.

    Returns
    -------
    Plan
        Rooms, walls (load-bearing per ``Pset_WallCommon``) and, as outline, the rooms'
        bounding box.

    Raises
    ------
    InvalidInput
        Unreadable file, no space, ambiguous storey, unlabelled space.
    UnsupportedInput
        ``ifcopenshell`` missing, a space that is not an axis-aligned rectangle or whose
        footprint needs a geometry kernel, a load-bearing wall without an axis.
    """
    model = _open(path)
    scale = float(_ifcopenshell().util.unit.calculate_unit_scale(model))
    rooms = _rooms(_on_storey(model, "IfcSpace", storey), scale, default_type)
    walls = _walls(_on_storey(model, "IfcWall", storey), scale, only_load_bearing=False)
    x0, y0 = min(r.x for r in rooms), min(r.y for r in rooms)
    x1, y1 = max(r.x + r.w for r in rooms), max(r.y + r.h for r in rooms)
    outline = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return Plan(rooms=rooms, walls=walls, outline=outline)


def load_ifc_structure(path: Path | str, *, storey: str | None = None) -> Structure:
    """Read the load-bearing walls and the columns of one floor of an IFC model.

    Parameters
    ----------
    path : Path or str
        The ``.ifc`` file.
    storey : str, optional
        ``Name`` of the storey to read; needed when spaces sit on several.

    Returns
    -------
    Structure
        Walls with ``Pset_WallCommon.LoadBearing`` true, and ``IfcColumn`` origins.

    Raises
    ------
    InvalidInput
        Unreadable file, or ambiguous storey.
    UnsupportedInput
        ``ifcopenshell`` missing, or a load-bearing wall without an axis.
    """
    model = _open(path)
    util = _ifcopenshell().util
    scale = float(util.unit.calculate_unit_scale(model))
    walls = _walls(_on_storey(model, "IfcWall", storey), scale, only_load_bearing=True)
    columns = tuple(
        _place(util.placement.get_local_placement(column.ObjectPlacement), [(0.0, 0.0)], scale)[0]
        for column in _on_storey(model, "IfcColumn", storey)
    )
    return Structure(load_bearing_walls=walls, columns=columns)
