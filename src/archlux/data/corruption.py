"""Controlled corruption of a valid plan — manufactures inputs to repair.

Why this module exists
-----------------------
A real corpus is **already valid**: 398 of 400 MSD apartments pass
``verify_exactly``. Measuring the "validity rate before / after ``legalize``"
on these plans therefore says nothing. Invalid inputs are needed whose **fault
is known**, which no corpus provides.

There are two ways to get them: the outputs of a generative model, or the
controlled corruption of a real plan. The second is reproducible down to the
seed, gives a large sample size, and above all **we know what was broken** —
which lets us measure whether the correction repairs the right thing, not
just whether it makes a plan valid.

What this module does **not** claim
------------------------------------
These perturbations are **not** a model of the errors of any particular
generator. They reproduce the *families* of faults reported in the
literature — overlaps, gaps, undersized rooms, offset partitions — without
calibrating their frequencies on a real model. Any publication must say so
and complement it with at least one public generator.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.types import Plan, Room

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MODES", "Corruption", "Mode", "corrupt"]

Mode = Literal["deplacer", "elargir", "retrecir", "aplatir"]

MODES: tuple[Mode, ...] = ("deplacer", "elargir", "retrecir", "aplatir")
"""The four fault families, and what each one produces.

===========  =========================================  ===========================
Mode         Perturbation                               Fault produced
===========  =========================================  ===========================
``deplacer``  translation of the room                    overlap **and** gap
``elargir``   ``w`` or ``h`` increased                    overlap
``retrecir``  ``w`` or ``h`` decreased                     gap
``aplatir``   ``h`` sharply decreased                      area below threshold
===========  =========================================  ===========================

``deplacer`` is closest to what a generator produces: it places a room
roughly in the right spot, which opens a gap on one side and an overlap on
the other.
"""

_TAILLE_MIN = 0.30
"""Floor, in metres, below which a corrupted room would be degenerate.

A room with zero thickness is not an invalid plan: it is a plan with no
geometry, which ``geom`` rejects before a correction can even be attempted.
"""


@dataclass(frozen=True, slots=True)
class Corruption:
    """A perturbation applied, as it can later be compared to the correction.

    Attributes
    ----------
    room_id : str
        Identifier of the affected room, as it appears in ``Plan.rooms``.
    amplitude : float
        Displacement actually applied, in metres. May be **smaller** than the
        requested amplitude if the :data:`_TAILLE_MIN` floor was hit; this
        value is the ground truth, not the request.
    """

    mode: Mode
    room_id: str
    amplitude: float
    axis: Literal["x", "y"]


def _perturber(
    room: Room, mode: Mode, amplitude: float, axis: Literal["x", "y"]
) -> tuple[Room, float]:
    """Apply a perturbation, and return the amplitude actually applied."""
    if mode == "deplacer":
        if axis == "x":
            return replace(room, x=room.x + amplitude), amplitude
        return replace(room, y=room.y + amplitude), amplitude
    if mode == "elargir":
        if axis == "x":
            return replace(room, w=room.w + amplitude), amplitude
        return replace(room, h=room.h + amplitude), amplitude
    if mode == "retrecir":
        if axis == "x":
            applique = min(amplitude, max(0.0, room.w - _TAILLE_MIN))
            return replace(room, w=room.w - applique), applique
        applique = min(amplitude, max(0.0, room.h - _TAILLE_MIN))
        return replace(room, h=room.h - applique), applique
    # aplatir: crush the larger dimension, to target the area.
    if room.w >= room.h:
        applique = min(amplitude, max(0.0, room.w - _TAILLE_MIN))
        return replace(room, w=room.w - applique), applique
    applique = min(amplitude, max(0.0, room.h - _TAILLE_MIN))
    return replace(room, h=room.h - applique), applique


def corrupt(
    plan: Plan,
    *,
    seed: int,
    amplitude: float = 0.50,
    n_pieces: int = 1,
    modes: Sequence[Mode] = MODES,
) -> tuple[Plan, tuple[Corruption, ...]]:
    """Perturb ``n_pieces`` rooms of a valid plan, reproducibly.

    Parameters
    ----------
    plan : Plan
        Starting plan, **assumed valid**. Nothing enforces it: corrupting an
        already invalid plan remains well defined, but the "before / after"
        measurement loses its meaning.
    seed : int
        Seed, **mandatory and with no default** (`ARCHITECTURE.md` §7). Two
        calls with the same seed on the same plan return exactly the same
        result.
    amplitude : float, optional
        Targeted magnitude of the perturbation, in metres. The *applied*
        amplitude is reported by each :class:`Corruption` and may be smaller.
    n_pieces : int, optional
        Number of distinct rooms to affect. Capped at the number of rooms.
    modes : sequence of Mode, optional
        Allowed fault families, drawn uniformly. Restricting to a single mode
        lets the correction be measured fault by fault.

    Returns
    -------
    tuple
        ``(corrupted_plan, corruptions)``. ``corrupted_plan`` **never** carries
        a certificate: it is an input to correct, not an output.

    Raises
    ------
    InvariantViolation
        Plan with no room, ``n_pieces < 1``, ``amplitude <= 0``, or empty
        ``modes``.

    Examples
    --------
    >>> from archlux.data.corruption import corrompre
    >>> from archlux.types import Plan, Room
    >>> plan = Plan(
    ...     rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),),
    ...     walls=(), openings=(),
    ...     outline=((0.0, 0.0), (6.0, 0.0), (6.0, 9.0), (0.0, 9.0)),
    ... )
    >>> abime, fautes = corrompre(plan, seed=17, modes=("elargir",))
    >>> len(fautes), fautes[0].mode, fautes[0].room_id
    (1, 'elargir', 'a')
    >>> abime.certificate is None
    True
    """
    if not plan.rooms:
        raise InvariantViolation(("plan with no room: nothing to corrupt",))
    if n_pieces < 1:
        raise InvariantViolation((f"n_pieces must be >= 1: {n_pieces}",))
    if amplitude <= 0.0:
        raise InvariantViolation((f"amplitude must be > 0: {amplitude}",))
    if not modes:
        raise InvariantViolation(("no corruption mode",))

    rng = np.random.default_rng(seed)
    # Sort by identifier before drawing: the order of ``plan.rooms`` must not
    # influence the result, otherwise the seed alone would not suffice to replay it.
    rangs = sorted(range(len(plan.rooms)), key=lambda i: plan.rooms[i].id)
    combien = min(n_pieces, len(rangs))
    choisis = [rangs[int(i)] for i in rng.choice(len(rangs), size=combien, replace=False)]

    rooms = list(plan.rooms)
    fautes: list[Corruption] = []
    for rang in sorted(choisis):
        mode = modes[int(rng.integers(len(modes)))]
        axis: Literal["x", "y"] = "x" if bool(rng.integers(2)) else "y"
        signe = 1.0 if mode != "deplacer" else float(rng.choice([-1.0, 1.0]))
        room, applique = _perturber(rooms[rang], mode, amplitude * signe, axis)
        if applique == 0.0:
            continue
        rooms[rang] = room
        fautes.append(Corruption(mode=mode, room_id=room.id, amplitude=float(applique), axis=axis))
    return replace(plan, rooms=tuple(rooms), certificate=None), tuple(fautes)


__getattr__ = lazy_aliases(
    __name__,
    {
        "corrompre": Alias(corrupt, "archlux.data.corruption.corrupt"),
    },
)
