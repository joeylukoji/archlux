"""Assemblage de la garantie probabiliste dans le certificat.

Ce module est la **seule** voie par laquelle une valeur d'éclairement entre dans un
:class:`archlux.types.Certificat`. Elle y entre toujours accompagnée de sa couverture et
de la taille du jeu de calibration : aucune valeur sans son incertitude.
"""

from __future__ import annotations

from math import isfinite

from archlux.erreurs import InvariantViole
from archlux.types import BornePerformance, Regime
from archlux.uq.conforme import Calibration, borner, quantile_conforme
from archlux.uq.derive import DiagnosticDerive

__all__ = ["Calibration", "bound_selected_plan", "check_calibration", "construire_borne"]


def construire_borne(
    valeur: float,
    calibration: Calibration,
    derive: DiagnosticDerive,
    *,
    incertitude: float,
    regime: Regime,
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
    incertitude : float
        ``σ̂`` of the point, **strictly positive**, for normalized calibration scores;
        ``1.0`` for raw ones. Mandatory (PLAN.md batch 1.6).
    regime : {"exchangeable", "selected"}
        See :func:`archlux.uq.conforme.borner`.

    Returns
    -------
    BornePerformance or None
        ``None`` signifie ``NON EVALUABLE`` : le système préfère ne rien affirmer
        plutôt qu'affirmer une couverture qu'il ne peut pas tenir.

    Notes
    -----
    Deux pièges que la signature ne rattrape pas :

    - **``incertitude`` must match the calibration.** The only calibration builder of
      the repository, :meth:`archlux.uq.conforme.CalibrateurConforme.ajuster`, divides
      the scores by ``σ``; ``Calibration`` does not record it, the caller does.
    - **``derive.echangeable`` est un non-rejet, pas une preuve d'échangeabilité.**
      Il est ici traité comme une autorisation de publier ; à faible effectif, le test
      de :func:`archlux.uq.derive.controler_derive` n'a pratiquement aucune puissance.
      Le certificat n'affiche donc pas « pas de dérive » mais « dérive non détectée ».
    """
    if not derive.echangeable:
        return None
    return borner(valeur, calibration, incertitude=incertitude, regime=regime)


def check_calibration(calibration: object) -> None:
    """Refuse, before any solving, a calibration that could not give a finite bound.

    Raises
    ------
    InvariantViole
        Not a :class:`Calibration`, non-finite scores, ``alpha`` outside ``]0, 1[`` or a
        set too small for ``alpha``: the conformal quantile is computed once here.
    """
    if not isinstance(calibration, Calibration):
        raise InvariantViole(
            (f"calibration must be a Calibration, got {type(calibration).__name__}",)
        )
    quantile_conforme(calibration.scores, calibration.alpha)


def bound_selected_plan(
    value: float, calibration: Calibration, *, uncertainty: float
) -> BornePerformance | None:
    """Conformal interval of a plan **chosen by the optimizer** (PLAN.md batch 1.6).

    The interval is computed as for an exchangeable plan, but it is labelled
    ``regime="selected"``: the plan maximizes the prediction, so it is not exchangeable
    with the calibration set and its nominal coverage is not guaranteed (winner's
    curse, AUDIT.md §5.3). No drift test is run: it would need the true value of the
    chosen plan, which only the oracle can give. The report says so; a procedure valid
    under selection is PLAN.md phase 6.4.

    Parameters
    ----------
    value : float
        Prediction of the surrogate at the returned plan.
    calibration : Calibration
        Scores normalized by ``σ`` (:meth:`archlux.uq.conforme.CalibrateurConforme.ajuster`).
    uncertainty : float
        ``σ̂`` of the surrogate at the returned plan, strictly positive.

    Returns
    -------
    BornePerformance or None
        With ``regime="selected"`` and ``coverage_guaranteed`` false; ``None`` (the
        report says ``NON EVALUABLE``) when the surrogate gives no positive finite
        ``σ̂`` at the plan, rather than discarding a plan whose geometry is proved.
    """
    if not (isfinite(uncertainty) and uncertainty > 0.0):
        return None
    return borner(value, calibration, incertitude=uncertainty, regime="selected")
