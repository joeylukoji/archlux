"""Imputer des baies manquantes : centrées sur chaque mur, ratio documenté."""

from __future__ import annotations

from dataclasses import replace

from archlux.types import Opening, Plan, Wall

__all__ = ["RATIO_BAIE_DEFAUT", "imputer_ouvertures"]

RATIO_BAIE_DEFAUT = 0.30
"""Largeur relative tirée de la distribution observée (jalon 4, jeu propre vs imputé)."""


def imputer_ouvertures(plan: Plan, *, ratio: float = RATIO_BAIE_DEFAUT) -> Plan:
    """Ajouter une baie centrée sur chaque mur sans ouverture.

    Ne touche pas aux baies déjà présentes. L'effet de cette imputation sur la
    calibration doit être mesuré à part (`docs/donnees/imputation.md`).
    """
    murs_occupes = {o.wall_id for o in plan.ouvertures}
    nouvelles: list[Opening] = list(plan.ouvertures)
    murs: tuple[Wall, ...] = plan.murs
    if not murs and len(plan.contour) >= 2:
        contour = (*plan.contour, plan.contour[0])
        murs = tuple(
            Wall(id=f"contour-{i}", a=contour[i], b=contour[i + 1])
            for i in range(len(plan.contour))
        )
    for mur in murs:
        if mur.id in murs_occupes:
            continue
        nouvelles.append(
            Opening(
                id=f"impute-{mur.id}",
                wall_id=mur.id,
                s=0.5,
                relative_width=ratio,
            )
        )
    return replace(plan, murs=murs, ouvertures=tuple(nouvelles))
