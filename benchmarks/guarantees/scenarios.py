"""Deterministic generator of realistic legalization scenarios.

Each scenario is a valid apartment plan together with a context that actually
constrains it:

- the outline is a rectangle of 10-16 m by 7-12 m;
- rooms come from recursive guillotine cuts on a 10 cm grid, so the plan tiles its
  outline exactly and every room side is at least ``MIN_SIDE_M``;
- the **first cut spans the whole building** and is declared load-bearing, like a real
  bearing partition (refend);
- every room type present gets a minimum area between 70 % and 100 % of its smallest
  room, so the input is valid and the constraint is tight.

``perturb`` adds a few centimetres of noise, to mimic a nearly valid generated plan.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from archlux.types import Contexte, Mur, Orientation, Piece, Plan, Referentiel, Structure

GRID_M = 0.10
MIN_SIDE_M = 2.0
ROOM_TYPES = ("chambre", "cuisine", "sdb", "wc", "couloir")
"""Current (French) room type names; they follow the glossary rename in batch E5."""


@dataclass(frozen=True, slots=True)
class Scenario:
    """A valid plan and the context it is valid under."""

    name: str
    plan: Plan
    context: Contexte


def _cut(
    rng: np.random.Generator, rect: tuple[float, float, float, float]
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float], str, float]:
    """Split ``rect`` across its longer side at a random grid position."""
    x, y, w, h = rect
    vertical = w >= h
    span = w if vertical else h
    steps = round((span - 2 * MIN_SIDE_M) / GRID_M)
    offset = MIN_SIDE_M + GRID_M * int(rng.integers(0, steps + 1))
    if vertical:
        return (x, y, offset, h), (x + offset, y, w - offset, h), "v", x + offset
    return (x, y, w, offset), (x, y + offset, w, h - offset), "h", y + offset


def generate(seed: int, index: int) -> Scenario:
    """Scenario number ``index`` of the series defined by ``seed``."""
    rng = np.random.default_rng([seed, index])
    width = GRID_M * int(rng.integers(100, 161))
    height = GRID_M * int(rng.integers(70, 121))
    target_rooms = int(rng.integers(4, 9))

    rects = [(0.0, 0.0, width, height)]
    first_cut: tuple[str, float] | None = None
    while len(rects) < target_rooms:
        splittable = [r for r in rects if max(r[2], r[3]) >= 2 * MIN_SIDE_M]
        if not splittable:
            break
        largest = max(splittable, key=lambda r: r[2] * r[3])
        rects.remove(largest)
        a, b, axis, position = _cut(rng, largest)
        rects += [a, b]
        first_cut = first_cut or (axis, position)
    assert first_cut is not None, "outline too small to split"

    kinds = ["sejour", *(str(rng.choice(ROOM_TYPES)) for _ in rects[1:])]
    rooms = tuple(
        Piece(id=f"r{i}", type=kind, x=round(x, 2), y=round(y, 2), w=round(w, 2), h=round(h, 2))
        for i, (kind, (x, y, w, h)) in enumerate(zip(kinds, rects, strict=True))
    )

    axis, position = first_cut
    ends = (
        ((position, 0.0), (position, height))
        if axis == "v"
        else ((0.0, position), (width, position))
    )
    wall = Mur(id="refend", a=ends[0], b=ends[1], porteur=True)

    smallest: dict[str, float] = {}
    for room in rooms:
        smallest[room.type] = min(smallest.get(room.type, float("inf")), room.w * room.h)
    ratio = float(rng.uniform(0.7, 1.0))
    outline = ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    context = Contexte(
        structure=Structure(murs_porteurs=(wall,)),
        orientation=Orientation(deg=float(rng.uniform(0.0, 360.0))),
        contour=outline,
        referentiel=Referentiel(
            aires_min=tuple(sorted((k, round(ratio * a, 4)) for k, a in smallest.items())),
            largeur_min=1.0,
        ),
    )
    plan = Plan(pieces=rooms, murs=(wall,), ouvertures=(), contour=outline)
    return Scenario(name=f"s{seed}-{index:04d}", plan=plan, context=context)


def perturb(plan: Plan, *, seed: int, amplitude_m: float = 0.03) -> Plan:
    """Move every room coordinate by up to ``amplitude_m``: a nearly valid plan."""
    rng = np.random.default_rng(seed)
    noisy = tuple(
        Piece(
            id=r.id,
            type=r.type,
            x=r.x + float(rng.uniform(-amplitude_m, amplitude_m)),
            y=r.y + float(rng.uniform(-amplitude_m, amplitude_m)),
            w=r.w + float(rng.uniform(-amplitude_m, amplitude_m)),
            h=r.h + float(rng.uniform(-amplitude_m, amplitude_m)),
        )
        for r in plan.pieces
    )
    return Plan(pieces=noisy, murs=plan.murs, ouvertures=plan.ouvertures, contour=plan.contour)
