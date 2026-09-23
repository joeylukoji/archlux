"""Rapport stratifié par orientation — obligatoire, sans agrégat global seul."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from archlux.bench.graines import deriver
from archlux.bench.run import Resultat
from archlux.bench.stats import Intervalle, bootstrap_apparie
from archlux.erreurs import InvariantViole
from archlux.orient.circulaire import stratifier

__all__ = ["N_REPLICATIONS", "RapportBanc", "StrateOrientation", "report"]

N_REPLICATIONS = 2000
"""Réplications bootstrap par strate.

Une borne à 2,5 % estimée sur 199 réplications est le 5ᵉ ordre statistique : son
erreur de Monte-Carlo domine la largeur qu'on prétend publier. 2000 ramène cette
erreur sous le bruit d'échantillonnage pour une table d'article.
"""


@dataclass(frozen=True, slots=True)
class StrateOrientation:
    """Agrégats d'une rose des vents (secteur)."""

    secteur: str
    n: int
    scores_par_methode: Mapping[str, Intervalle]


@dataclass(frozen=True, slots=True)
class RapportBanc:
    """Sortie de :func:`report` : une strate par secteur, y compris les vides."""

    strates: tuple[StrateOrientation, ...]


def _secteur_par_degre(
    degres: Iterable[float], *, n_secteurs: int
) -> dict[float, str]:
    """Associer chaque azimut distinct à son secteur, via ``orient.stratifier``.

    ``stratifier`` rend des valeurs groupées, pas des indices : on l'interroge donc
    azimut distinct par azimut distinct. Deux azimuts égaux tombent toujours dans le
    même secteur, donc ``O(distincts)`` appels suffisent.
    """
    correspondance: dict[float, str] = {}
    for deg in degres:
        groupes = stratifier([deg], n_secteurs=n_secteurs)
        correspondance[deg] = next(
            nom for nom, valeurs in groupes.items() if valeurs.size
        )
    return correspondance


def report(
    resultat: Resultat,
    *,
    seed: int,
    n_secteurs: int = 8,
) -> RapportBanc:
    """Agréger **après** les bruts, stratifié par orientation.

    La stratification est imposée (`MILESTONE-6.md` §5) : pas de résumé global unique.

    **Limite connue** : les intervalles sont marginaux, un par couple
    (secteur × méthode). Lire ``n_secteurs × n_méthodes`` intervalles à 95 % comme
    autant de conclusions simultanées surestime la significativité ; corriger la
    famille avec :func:`archlux.bench.stats.holm` avant toute publication.
    """
    if n_secteurs < 1:
        raise InvariantViole(("n_secteurs doit être ≥ 1",))

    # Le binning vient de ``stratifier`` seul : le réimplémenter ici laissait deux
    # conventions de secteur diverger en silence à la moindre retouche d'``orient``.
    noms = tuple(stratifier([0.0], n_secteurs=n_secteurs).keys())
    secteur_de = _secteur_par_degre(
        {ligne.orientation_deg for ligne in resultat.lignes}, n_secteurs=n_secteurs
    )

    par_secteur: dict[str, dict[str, list[float]]] = {
        nom: defaultdict(list) for nom in noms
    }
    for ligne in resultat.lignes:
        par_secteur[secteur_de[ligne.orientation_deg]][ligne.methode].append(
            ligne.score
        )

    strates: list[StrateOrientation] = []
    for nom in noms:
        scores: dict[str, Intervalle] = {}
        for methode, valeurs in sorted(par_secteur[nom].items()):
            if len(valeurs) >= 2:
                zeros = [0.0] * len(valeurs)
                ic = bootstrap_apparie(
                    valeurs,
                    zeros,
                    # Sous-graine nommée plutôt que ``seed + i`` : deux strates
                    # voisines ne se retrouvent pas avec des graines adjacentes.
                    seed=deriver(seed, f"strate:{nom}:{methode}"),
                    n_replications=N_REPLICATIONS,
                    alpha=0.05,
                )
                scores[methode] = Intervalle(
                    valeur=float(np.mean(valeurs)), bas=ic.bas, haut=ic.haut
                )
            elif len(valeurs) == 1:
                # Intervalle **dégénéré** : une observation ne borne rien. Il est
                # rendu de largeur nulle et doit être lu comme « non estimable ».
                v = float(valeurs[0])
                scores[methode] = Intervalle(valeur=v, bas=v, haut=v)
        n_plans = max((len(v) for v in par_secteur[nom].values()), default=0)
        strates.append(
            StrateOrientation(secteur=nom, n=n_plans, scores_par_methode=scores)
        )
    return RapportBanc(strates=tuple(strates))
