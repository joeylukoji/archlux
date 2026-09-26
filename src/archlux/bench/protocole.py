"""Protocole d'évaluation : découpages figés, graines explicites, résultats bruts.

Personne n'importe ``bench`` : c'est la feuille de l'arbre de dépendances
(`ARCHITECTURE.md` §5). Un import de ``bench`` depuis le noyau fait échouer la CI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archlux.data.decoupage import Decoupage, charger_decoupage
from archlux.errors import InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from archlux.light.protocole import Surrogate
    from archlux.types import Plan

__all__ = ["Decoupage", "charger_decoupage", "compare"]


def compare(
    *,
    plans: Sequence[Plan],
    methods: Sequence[Surrogate],
    evaluate_by: Callable[[Plan, Surrogate], float],
) -> tuple[float, ...]:
    """Comparer des substituts avec un évaluateur **externe** obligatoire.

    Évaluer un réseau par le réseau lui-même est une erreur circulaire
    (`MILESTONE-4.md` §8). ``evaluate_by`` est typiquement l'oracle gelé.
    **Sans défaut** : omettre l'argument lève ``TypeError``.

    ``Surrogate`` est vectoriel : le callback doit transformer le ``Plan`` en
    vecteur ``(x, y, w, h)`` (voir :func:`archlux.light.jetons.plan_vers_vecteur`)
    avant d'appeler ``evaluate``.

    **Limite connue** : la valeur rendue est une moyenne **nue**, sans intervalle, ce
    que `ARCHITECTURE.md` §7 et §10 proscrivent pour une métrique publiée. Utiliser
    :func:`archlux.bench.rapport.report` (stratifié, bootstrap) pour toute table
    d'article ; ``compare`` ne sert qu'à ordonner grossièrement des substituts.

    Raises
    ------
    TypeError
        ``evaluate_by`` manquant.
    InvariantViolation
        ``plans`` vide. Un échantillon vide n'a pas de score moyen : rendre ``0.0``
        fabriquait une mesure et faisait passer un substitut pour le pire de tous.
    """
    if not plans:
        raise InvariantViolation(("plans vide : aucune moyenne à calculer",))
    return tuple(
        sum(float(evaluate_by(plan, methode)) for plan in plans) / len(plans) for methode in methods
    )
