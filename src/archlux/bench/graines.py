"""Dérivation déterministe de graines. Aucune graine implicite nulle part.

Une graine par exécution, dérivée en sous-graines nommées : deux composantes ne partagent
jamais un flux aléatoire, et une exécution se rejoue exactement.

Le hachage est **cryptographique et sans sel** (BLAKE2b tronqué). C'est délibéré :
``hash()`` de Python est randomisé d'un processus à l'autre, ce qui rendrait la
dérivation non reproductible — exactement ce que ce module existe pour empêcher.
"""

from __future__ import annotations

from archlux.seeds import derive

__all__ = ["deriver"]

def deriver(seed: int, nom: str) -> int:
    """Dériver une sous-graine stable à partir d'une graine racine et d'un nom.

    Parameters
    ----------
    seed : int
        Graine racine de l'exécution, telle qu'inscrite au manifeste.
    nom : str
        Nom du flux (``"calibration"``, ``"permutation"``, …). Deux noms distincts
        donnent deux flux indépendants ; le même nom redonne toujours le même flux.

    Returns
    -------
    int
        Sous-graine dans ``[0, 2**32)``, stable d'une version et d'une machine à
        l'autre.

    Complexity
    ----------
    O(len(nom)).

    Examples
    --------
    >>> from archlux.bench.graines import deriver
    >>> deriver(17, "calibration") == deriver(17, "calibration")
    True
    >>> deriver(17, "calibration") == deriver(17, "permutation")
    False
    """
    return derive(seed, nom)
