"""Traduction des prix duaux en langage d'architecte.

Un prix dual brut est « le nombre de la ligne 47 ». Croisé avec ``Polytope.origines``,
c'est « le mur porteur de l'axe 3 vous coûte 4,1 points de sDA ». Cette traduction est
le principal apport utilisable du certificat : elle dit **quelle contrainte relâcher**.

Les prix sont valides **localement** (quelques dizaines de centimètres). Un diagnostic
sans cet intervalle serait trompeur.
"""

from __future__ import annotations

import numpy as np

from archlux.geom.polytope import Polytope

__all__ = ["traduire_duaux"]

_PHRASE = (
    "{libelle} : relâchement unitaire ≈ {prix:+.2f} (validité locale, quelques dizaines de cm)"
)


def traduire_duaux(
    duaux: np.ndarray, poly: Polytope, *, seuil: float = 1e-6, n_max: int = 10
) -> tuple[tuple[str, float], ...]:
    """Apparier chaque prix dual non nul avec le libellé de sa contrainte.

    Parameters
    ----------
    duaux : numpy.ndarray
        Prix duaux, dans l'ordre des lignes de ``poly.A``.
    poly : Polytope
        Fournit ``origines``, indispensable et non reconstructible après coup.
    seuil : float, optional
        En-deçà, la contrainte est considérée inactive et n'est pas rapportée.
    n_max : int, optional
        Nombre de contraintes rapportées, les plus coûteuses d'abord.

    Returns
    -------
    tuple of (str, float)
        Paires ``(phrase lisible, coût)``, triées par valeur absolue décroissante.
        Chaque phrase mentionne l'intervalle de validité locale.
    """
    vecteur = np.asarray(duaux, dtype=float).ravel()
    paires: list[tuple[str, float]] = []
    for libelle, brut in zip(poly.origines, vecteur, strict=True):
        prix = float(brut)
        if abs(prix) <= seuil:
            continue
        phrase = _PHRASE.format(libelle=libelle, prix=prix)
        paires.append((phrase, prix))
    paires.sort(key=lambda paire: -abs(paire[1]))
    return tuple(paires[:n_max])
