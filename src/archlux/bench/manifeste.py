"""Émission du manifeste de reproductibilité.

Toute exécution en produit un, sans exception. Un résultat sans manifeste n'est pas
reproductible, et un résultat non reproductible n'est pas un résultat.
"""

from __future__ import annotations

import datetime as dt
import sys
from importlib.metadata import PackageNotFoundError, version

from archlux._version import __version__
from archlux.types import Manifeste, ModeleTrace

__all__ = ["emettre"]

_PAQUETS_SUIVIS = ("numpy", "scipy", "networkx", "shapely", "ortools", "torch")
"""Paquets dont la version change les résultats numériques, donc les conclusions.

``torch`` y figure sans être importé : seule sa version est relevée, et seulement s'il
est déjà installé. Relever une version n'est pas charger une bibliothèque.
"""


def _version_installee(nom: str) -> str | None:
    """Version installee d'un paquet, ou ``None`` s'il est absent."""
    try:
        return version(nom)
    except PackageNotFoundError:
        return None


def _environnement() -> tuple[tuple[str, str], ...]:
    """Versions de Python et des paquets présents, triées.

    Un paquet optionnel absent est **omis**, jamais noté ``"absent"`` : le manifeste
    décrit ce qui a servi, pas ce qui manquait.
    """
    releve = {"python": sys.version.split()[0]}
    for nom in _PAQUETS_SUIVIS:
        version = _version_installee(nom)
        if version is not None:
            releve[nom] = version
    return tuple(sorted(releve.items()))


def emettre(
    *,
    seed: int,
    empreinte_donnees: str | None = None,
    decoupage: str | None = None,
    parametres: dict[str, str] | None = None,
    modele: ModeleTrace | None = None,
) -> Manifeste:
    """Construire le manifeste de l'exécution courante.

    Parameters
    ----------
    seed : int
        Graine racine. **Obligatoire, sans défaut** (`ARCHITECTURE.md` §7) : une graine
        implicite est une graine perdue, et l'exécution cesse d'être rejouable.
    empreinte_donnees : str or None, optional
        ``sha256`` du corpus utilisé.
    decoupage : str or None, optional
        Identifiant du découpage figé, par exemple ``"splits/v2"``.
    parametres : dict of str to str or None, optional
        Paramètres de l'exécution. Ils sont figés en paires **triées** : sans tri,
        l'empreinte du manifeste change d'une exécution à l'autre et n'identifie plus
        rien.
    modele : ModeleTrace or None, optional
        Empreinte des poids et taille de calibration (obligatoire pour ``bench.run``).

    Returns
    -------
    Manifeste
        Version, horodatage UTC, graine, empreintes et versions d'environnement.

    Guarantees
    ----------
    - Aucune garantie de calcul : ce type est une **trace**. Il ne dit pas qu'un
      résultat est correct, seulement dans quelles conditions il a été produit.

    Complexity
    ----------
    O(k) sur le nombre de paquets suivis.
    """
    return Manifeste(
        version=__version__,
        horodatage=dt.datetime.now(dt.UTC).isoformat(),
        graine=seed,
        empreinte_donnees=empreinte_donnees,
        decoupage=decoupage,
        environnement=_environnement(),
        parametres=tuple(sorted((parametres or {}).items())),
        modele=modele,
    )
