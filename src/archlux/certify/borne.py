"""Assemblage de la garantie probabiliste dans le certificat.

Ce module est la **seule** voie par laquelle une valeur d'éclairement entre dans un
:class:`archlux.types.Certificat`. Elle y entre toujours accompagnée de sa couverture et
de la taille du jeu de calibration : aucune valeur sans son incertitude.
"""

from __future__ import annotations

from archlux.types import BornePerformance
from archlux.uq.conforme import Calibration, borner
from archlux.uq.derive import DiagnosticDerive

__all__ = ["construire_borne"]


def construire_borne(
    valeur: float,
    calibration: Calibration,
    derive: DiagnosticDerive,
    *,
    incertitude: float = 1.0,
) -> BornePerformance | None:
    """Construire la borne, ou ``None`` si la dérive invalide l'échangeabilité.

    Parameters
    ----------
    valeur : float
        Estimation ponctuelle.
    calibration : Calibration
        Jeu de scores conforme.
    derive : DiagnosticDerive
        Verdict d'échangeabilité. ``echangeable=False`` → ``None``.
    incertitude : float, optional
        ``σ̂`` du point, **strictement positif**, si les scores de calibration sont
        normalisés.

    Returns
    -------
    BornePerformance or None
        ``None`` signifie ``NON EVALUABLE`` : le système préfère ne rien affirmer
        plutôt qu'affirmer une couverture qu'il ne peut pas tenir.

    Notes
    -----
    Deux pièges que la signature ne rattrape pas :

    - **Le défaut ``incertitude=1.0`` n'est correct que pour une calibration non
      normalisée.** Le seul constructeur de calibration du dépôt,
      :meth:`archlux.uq.conforme.CalibrateurConforme.ajuster`, divise les scores par
      ``σ`` ; appelé avec le défaut, ce module publierait donc une marge à la mauvaise
      échelle sans le signaler. ``Calibration`` ne transporte pas l'information « ces
      scores sont normalisés » : c'est à l'appelant de la tenir.
    - **``derive.echangeable`` est un non-rejet, pas une preuve d'échangeabilité.**
      Il est ici traité comme une autorisation de publier ; à faible effectif, le test
      de :func:`archlux.uq.derive.controler_derive` n'a pratiquement aucune puissance.
      Le certificat n'affiche donc pas « pas de dérive » mais « dérive non détectée ».
    """
    if not derive.echangeable:
        return None
    return borner(valeur, calibration, incertitude=incertitude)
