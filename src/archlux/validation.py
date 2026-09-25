"""Validation of the arguments of the public functions, done once at the door.

PLAN.md phase 3.1. Everything below the door (``geom``, ``lmo``, ``solve``) may assume
finite numbers, positive sizes and unique ids; a violation found later surfaces as an
LP status or as ``InvariantViole``, which means "internal bug" and points the user at
the wrong place. Every refusal here is an :class:`~archlux.erreurs.InvalidInput` that
names the field.

Only what the solver cannot survive is checked. Whether the plan is *geometrically*
valid is the job of ``certify``, never of this module.
"""

from __future__ import annotations

import math
import warnings
from numbers import Real
from typing import TYPE_CHECKING

from archlux.erreurs import InvalidInput

if TYPE_CHECKING:
    from collections.abc import Iterable

    from archlux.types import Contexte, Plan, Point

__all__ = ["validate_inputs"]


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


def _outline(field: str, outline: Iterable[Point]) -> None:
    points = tuple(outline)
    if len(points) < 3:
        raise InvalidInput(field, f"needs at least 3 points, got {len(points)}")
    for index, point in enumerate(points):
        _point(f"{field}[{index}]", point)


def _rooms(plan: Plan) -> None:
    if not plan.pieces:
        raise InvalidInput("pieces", "the plan has no room", "add at least one Piece")
    seen: set[str] = set()
    for index, room in enumerate(plan.pieces):
        if not isinstance(room.id, str) or not room.id:
            raise InvalidInput(f"pieces[{index}].id", "must be a non-empty string")
        label = f"pieces[{room.id}]"
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
    for wall in plan.murs:
        _point(f"murs[{wall.id}].a", wall.a)
        _point(f"murs[{wall.id}].b", wall.b)
        # > 0 as in the JSON reader: the two doors must agree on what a wall is.
        _positive(f"murs[{wall.id}].epaisseur", wall.epaisseur)
    # Openings need no check here: ``Ouverture`` refuses its own ranges at construction.


def _context(ctx: Contexte) -> None:
    _finite("orientation.deg", ctx.orientation.deg)
    _non_negative("referentiel.largeur_min", ctx.referentiel.largeur_min)
    for type_piece, threshold in ctx.referentiel.aires_min:
        _non_negative(f"referentiel.aires_min[{type_piece}]", threshold)
    _outline("contexte.contour", ctx.contour)
    for wall in ctx.structure.murs_porteurs:
        _point(f"structure.murs_porteurs[{wall.id}].a", wall.a)
        _point(f"structure.murs_porteurs[{wall.id}].b", wall.b)
    for index, post in enumerate(ctx.structure.poteaux):
        _point(f"structure.poteaux[{index}]", post)


def _warn_unregulated_types(plan: Plan, ctx: Contexte) -> None:
    """Warn about room types the regulation has no threshold for.

    A typo such as ``"sejuor"`` silently removes the minimum-area requirement of the room
    (``Referentiel.a_min`` gives ``0.0`` for an unknown type). Only when the regulation
    lists thresholds: an empty one means "no regulation", not a typo.
    """
    known = {type_piece for type_piece, _ in ctx.referentiel.aires_min}
    if not known:
        return
    unknown = sorted({room.type for room in plan.pieces} - known)
    if unknown:
        warnings.warn(
            f"room types {unknown} have no minimum area in referentiel.aires_min "
            f"(known: {sorted(known)}): no minimum is enforced for them. "
            "Check for a typo, or add the type to the regulation",
            UserWarning,
            stacklevel=4,  # warn <- this <- validate_inputs <- legalize <- the caller
        )


def validate_inputs(
    plan: Plan,
    ctx: Contexte,
    *,
    budget: float | None = None,
    budget_reparation: int = 0,
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
    budget_reparation : int, optional
        Repair steps granted to the tiling grid recovery.

    Raises
    ------
    InvalidInput
        On the first problem found, naming its field: a non-finite or non-numeric
        value, a non-positive room size, a duplicate id, a plan without room, an
        outline with fewer than 3 points, a negative budget.

    Warns
    -----
    UserWarning
        A room type absent from ``referentiel.aires_min`` (when it lists any).
    """
    _rooms(plan)
    _walls(plan)
    _outline("contour", plan.contour)
    _context(ctx)
    if budget is not None:
        _non_negative("budget", budget)
    if isinstance(budget_reparation, bool) or not isinstance(budget_reparation, int):
        raise InvalidInput("budget_reparation", f"must be an int, got {budget_reparation!r}")
    if budget_reparation < 0:
        raise InvalidInput("budget_reparation", f"must be >= 0, got {budget_reparation}")
    _warn_unregulated_types(plan, ctx)
