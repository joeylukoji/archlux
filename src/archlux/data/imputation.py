"""Impute missing openings: centered on each wall, ratio documented."""

from __future__ import annotations

from dataclasses import replace

from archlux._deprecation import Alias, lazy_aliases
from archlux.types import Opening, Plan, Wall

__all__ = ["DEFAULT_OPENING_RATIO", "impute_openings"]

DEFAULT_OPENING_RATIO = 0.30
"""Relative width drawn from the observed distribution (milestone 4, clean vs imputed set)."""


def impute_openings(plan: Plan, *, ratio: float = DEFAULT_OPENING_RATIO) -> Plan:
    """Add an opening centered on each wall that has none.

    Does not touch openings already present. The effect of this imputation on
    calibration must be measured separately (`docs/donnees/imputation.md`).
    """
    murs_occupes = {o.wall_id for o in plan.openings}
    nouvelles: list[Opening] = list(plan.openings)
    walls: tuple[Wall, ...] = plan.walls
    if not walls and len(plan.outline) >= 2:
        outline = (*plan.outline, plan.outline[0])
        walls = tuple(
            Wall(id=f"outline-{i}", a=outline[i], b=outline[i + 1])
            for i in range(len(plan.outline))
        )
    for wall in walls:
        if wall.id in murs_occupes:
            continue
        nouvelles.append(
            Opening(
                id=f"impute-{wall.id}",
                wall_id=wall.id,
                s=0.5,
                relative_width=ratio,
            )
        )
    return replace(plan, walls=walls, openings=tuple(nouvelles))


__getattr__ = lazy_aliases(
    __name__,
    {
        "imputer_ouvertures": Alias(impute_openings, "archlux.data.imputation.impute_openings"),
        "RATIO_BAIE_DEFAUT": Alias(
            DEFAULT_OPENING_RATIO, "archlux.data.imputation.DEFAULT_OPENING_RATIO"
        ),
    },
)
