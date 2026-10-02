"""Validation of the arguments of the public functions, done once at the door.

PLAN.md phase 3.1. Everything below the door (``geom``, ``lmo``, ``solve``) may assume
finite numbers, positive sizes and unique ids; a violation found later surfaces as an
LP status or as ``InvariantViolation``, which means "internal bug" and points the user at
the wrong place. Every refusal here is an :class:`~archlux.errors.InvalidInput` that
names the field.

Only what the solver cannot survive is checked. Whether the plan is *geometrically*
valid is the job of ``certify``, never of this module.
"""

from __future__ import annotations

import math
import operator
import warnings
from dataclasses import replace
from numbers import Real
from typing import TYPE_CHECKING

from archlux.errors import InvalidInput
from archlux.tolerances import SNAP_M

if TYPE_CHECKING:
    from collections.abc import Iterable

    from archlux.types import Context, Plan, Point

__all__ = ["resolve_outline", "validate_inputs"]


def _is_number(value: object) -> bool:
    """A real number that is not a ``bool``: ``True`` as a width is a typo."""
    return isinstance(value, Real) and not isinstance(value, bool)


def _finite(field: str, value: object) -> float:
    """Return ``value`` as a float, or refuse it if it is not a finite number."""
    if not _is_number(value):
        raise InvalidInput(field, f"must be a number, got {type(value).__name__} {value!r}")
    number = float(value)  # type: ignore[arg-type]
    if not math.isfinite(number):
        raise InvalidInput(field, f"must be finite, got {number}")
    return number


def _positive(field: str, value: object) -> None:
    if _finite(field, value) <= 0.0:
        raise InvalidInput(field, f"must be > 0, got {value}")


def _non_negative(field: str, value: object) -> None:
    if _finite(field, value) < 0.0:
        raise InvalidInput(field, f"must be >= 0, got {value}")


def _point(field: str, point: object) -> None:
    if not isinstance(point, tuple | list) or len(point) != 2:
        raise InvalidInput(field, f"must be an (x, y) pair, got {point!r}")
    _finite(f"{field}.x", point[0])
    _finite(f"{field}.y", point[1])


def _integer(field: str, value: object) -> None:
    """Any integer, numpy's included (``operator.index``), but not a bool."""
    try:
        if isinstance(value, bool):
            raise TypeError
        operator.index(value)  # type: ignore[arg-type]
    except TypeError:
        raise InvalidInput(field, f"must be an int, got {value!r}") from None


def _outline(field: str, outline: Iterable[Point]) -> None:
    points = tuple(outline)
    if len(points) < 3:
        raise InvalidInput(field, f"needs at least 3 points, got {len(points)}")
    for index, point in enumerate(points):
        _point(f"{field}[{index}]", point)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    if max(xs) - min(xs) <= SNAP_M or max(ys) - min(ys) <= SNAP_M:
        # Caught later as an internal error ("degenerate outline") before this check.
        raise InvalidInput(field, "zero-width or zero-height outline", "give a real polygon")


def _rooms(plan: Plan) -> None:
    if not plan.rooms:
        raise InvalidInput("rooms", "the plan has no room", "add at least one Room")
    seen: set[str] = set()
    for index, room in enumerate(plan.rooms):
        if not isinstance(room.id, str) or not room.id:
            raise InvalidInput(f"rooms[{index}].id", "must be a non-empty string")
        label = f"rooms[{room.id}]"
        if room.id in seen:
            raise InvalidInput(
                f"{label}.id", "duplicate room id", "room ids must be unique in a plan"
            )
        seen.add(room.id)
        _finite(f"{label}.x", room.x)
        _finite(f"{label}.y", room.y)
        _positive(f"{label}.w", room.w)
        _positive(f"{label}.h", room.h)


def _walls(plan: Plan) -> None:
    for wall in plan.walls:
        _point(f"walls[{wall.id}].a", wall.a)
        _point(f"walls[{wall.id}].b", wall.b)
        # > 0 as in the JSON reader: the two doors must agree on what a wall is.
        _positive(f"walls[{wall.id}].thickness", wall.thickness)
    # Openings need no check here: ``Opening`` refuses its own ranges at construction.


def _context(ctx: Context) -> None:
    from archlux.types import Orientation, Regulation, Structure

    for name, kind in (
        ("structure", Structure),
        ("orientation", Orientation),
        ("regulation", Regulation),
    ):
        if not isinstance(getattr(ctx, name), kind):
            raise InvalidInput(
                f"context.{name}",
                f"must be a {kind.__name__}, got {type(getattr(ctx, name)).__name__}",
                "build Context with keywords: Context(structure=..., orientation=..., "
                "regulation=..., outline=...)",
            )
    _finite("orientation.deg", ctx.orientation.deg)
    _non_negative("regulation.min_width", ctx.regulation.min_width)
    for room_type, threshold in ctx.regulation.min_areas:
        _non_negative(f"regulation.min_areas[{room_type}]", threshold)
    for wall in ctx.structure.load_bearing_walls:
        _point(f"structure.load_bearing_walls[{wall.id}].a", wall.a)
        _point(f"structure.load_bearing_walls[{wall.id}].b", wall.b)
    for index, post in enumerate(ctx.structure.columns):
        _point(f"structure.columns[{index}]", post)


def _outlines(plan: Plan, ctx: Context) -> None:
    """Each outline given must be a polygon, and at least one of the two must be given."""
    for field, outline in (("outline", plan.outline), ("context.outline", ctx.outline)):
        if outline:
            _outline(field, outline)
    if not (plan.outline or ctx.outline):
        raise InvalidInput(
            "outline",
            "neither the plan nor the context has an outline",
            "give Context.outline or Plan.outline",
        )


def resolve_outline(plan: Plan, ctx: Context) -> Context:
    """The context with its outline filled in from the plan when it has none.

    An outline in the context wins over the plan's: it is the site, the plan's own is
    what the generator drew. Call after :func:`validate_inputs`.
    """
    return ctx if ctx.outline else replace(ctx, outline=plan.outline)


def _warn_unregulated_types(plan: Plan, ctx: Context, stacklevel: int) -> None:
    """Warn about room types the regulation has no threshold for.

    A typo such as ``"sejuor"`` silently removes the minimum-area requirement of the room
    (``Regulation.min_area`` gives ``0.0`` for an unknown type). Only when the regulation
    lists thresholds: an empty one means "no regulation", not a typo.
    """
    known = {room_type for room_type, _ in ctx.regulation.min_areas}
    if not known:
        return
    unknown = sorted({room.type for room in plan.rooms} - known)
    if unknown:
        warnings.warn(
            f"room types {unknown} have no minimum area in regulation.min_areas "
            f"(known: {sorted(known)}): no minimum is enforced for them. "
            "Check for a typo, or add the type to the regulation",
            UserWarning,
            stacklevel=stacklevel + 2,  # this <- validate_inputs <- (stacklevel frames)
        )


def validate_inputs(
    plan: Plan,
    ctx: Context,
    *,
    budget: float | None = None,
    repair_budget: int = 0,
    stacklevel: int = 3,
) -> None:
    """Refuse a malformed plan, context or option before any solving.

    Parameters
    ----------
    plan : Plan
        Proposed plan.
    ctx : Contexte
        Structure, orientation, outline, regulation.
    budget : float or None, optional
        Displacement budget in metres; ``None`` means no budget.
    repair_budget : int, optional
        Repair steps granted to the tiling grid recovery.
    stacklevel : int, optional
        Where the type warning points, counted from the caller of this function as for
        :func:`warnings.warn` (``2`` is that caller's caller). Each public entry point
        passes the depth that lands on *its* caller.

    Raises
    ------
    InvalidInput
        On the first problem found, naming its field: a non-finite or non-numeric
        value, a non-positive room size, a duplicate id, a plan without room, no outline
        at all or one with fewer than 3 points, a negative budget.

    Warns
    -----
    UserWarning
        A room type absent from ``referentiel.min_areas`` (when it lists any).
    """
    _rooms(plan)
    _walls(plan)
    _outlines(plan, ctx)
    _context(ctx)
    if budget is not None:
        _non_negative("budget", budget)
    _integer("repair_budget", repair_budget)
    if repair_budget < 0:
        raise InvalidInput("repair_budget", f"must be >= 0, got {repair_budget}")
    _warn_unregulated_types(plan, ctx, stacklevel)
