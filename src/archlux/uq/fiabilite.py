"""Diagrammes de fiabilité et score CRPS — sans aucune figure matplotlib.

Le diagnostic est un tableau ``(nominal, empirique)``. Le tracer est l'affaire du
carnet d'expérience, pas du noyau.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.special import erf

from archlux.erreurs import InvariantViole
from archlux.types import Regime
from archlux.uq.conforme import CalibrateurConforme, quantile_conforme

__all__ = [
    "CoverageReport",
    "crps",
    "diagramme_fiabilite",
    "measure_coverage",
    "stratifier_par_orientation",
]

_SIGMA_MIN = 1e-12
_N_SECTEURS = 8


def crps(predictions: np.ndarray, verites: np.ndarray, incertitudes: np.ndarray) -> float:
    """CRPS gaussien moyen (Gneiting & Raftery), en unité de l'indicateur.

    Parameters
    ----------
    predictions, verites, incertitudes : numpy.ndarray
        ``μ``, ``y``, ``σ`` point par point.

    Returns
    -------
    float
        Plus petit est meilleur. ``σ`` trop large ou trop étroit dégrade le score.
    """
    mu = np.asarray(predictions, dtype=float).ravel()
    y = np.asarray(verites, dtype=float).ravel()
    sigma = np.maximum(np.asarray(incertitudes, dtype=float).ravel(), _SIGMA_MIN)
    if mu.size != y.size or mu.size != sigma.size or mu.size == 0:
        raise InvariantViole(("tableaux CRPS de longueurs incompatibles",))
    z = (y - mu) / sigma
    pdf = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + erf(z / math.sqrt(2.0)))
    termes = sigma * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(math.pi))
    return float(np.mean(termes))


def diagramme_fiabilite(
    predictions: np.ndarray,
    verites: np.ndarray,
    incertitudes: np.ndarray,
    niveaux: np.ndarray | None = None,
    *,
    scores_calibration: np.ndarray | None = None,
) -> np.ndarray:
    """Couverture empirique en fonction de la couverture nominale.

    Parameters
    ----------
    predictions, verites, incertitudes : numpy.ndarray
        Même convention que :func:`crps`. Ce sont les points **évalués**.
    niveaux : numpy.ndarray or None, optional
        Niveaux nominaux dans ``(0, 1)``. Défaut : 20 points de 0,50 à 0,99.
    scores_calibration : numpy.ndarray or None, optional
        Scores de non-conformité d'un jeu de calibration **disjoint**. Fournis, les
        quantiles conformes en sont tirés et la couverture est mesurée hors
        échantillon : le diagramme devient informatif. Absents (défaut), le
        comportement historique est conservé — voir les notes.

    Returns
    -------
    numpy.ndarray
        Shape ``(n_niveaux, 2)`` : colonne 0 = nominal, colonne 1 = empirique.
        Les niveaux trop exigeants pour ``n`` reçoivent ``nan``.

    Notes
    -----
    **Sans ``scores_calibration``, la colonne empirique est une tautologie.** Le
    quantile ``q̂`` est alors calculé sur les scores mêmes dont on mesure la couverture ;
    par construction, ``mean(scores ≤ q̂) = ceil((n + 1)(1 − α)) / n``, indépendamment
    de la qualité de ``σ̂``. Un ``σ̂`` constant, aberrant ou tiré au hasard donne
    exactement la même courbe. Ce mode ne sert donc qu'à vérifier l'arithmétique du
    quantile, jamais à valider la calibration : toute figure publiée doit passer un jeu
    de calibration disjoint.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    verite = np.asarray(verites, dtype=float).ravel()
    sigma = np.maximum(np.asarray(incertitudes, dtype=float).ravel(), _SIGMA_MIN)
    if pred.size != verite.size or pred.size != sigma.size or pred.size == 0:
        raise InvariantViole(("tableaux du diagramme de longueurs incompatibles",))
    if niveaux is None:
        cibles = np.linspace(0.50, 0.99, 20)
    else:
        cibles = np.asarray(niveaux, dtype=float).ravel()
    scores = np.abs(verite - pred) / sigma
    reference = (
        scores
        if scores_calibration is None
        else np.asarray(scores_calibration, dtype=float).ravel()
    )
    lignes: list[list[float]] = []
    for gamma in cibles:
        alpha = 1.0 - float(gamma)
        try:
            q_chapeau = quantile_conforme(reference, alpha)
        except InvariantViole:
            lignes.append([float(gamma), float("nan")])
            continue
        empirique = float(np.mean(scores <= q_chapeau))
        lignes.append([float(gamma), empirique])
    return np.asarray(lignes, dtype=float)


def stratifier_par_orientation(
    degres: np.ndarray, *, n_secteurs: int = _N_SECTEURS
) -> dict[int, np.ndarray]:
    """Indices par secteur d'azimut, pour une couverture stratifiée.

    Parameters
    ----------
    degres : numpy.ndarray
        Azimuts en degrés.
    n_secteurs : int, optional
        Découpage (défaut 8).

    Returns
    -------
    dict of int to numpy.ndarray
        Secteur → indices. Le secteur ``k`` couvre ``[k·360/n, (k+1)·360/n[``.

    Notes
    -----
    Les secteurs sont **alignés sur les bords**, pas centrés : le secteur 0 est
    ``[0°, 45°[`` et non la rose des vents « N » ``[-22,5°, 22,5°[``. Deux azimuts
    voisins du nord (1° et 359°) tombent donc dans des secteurs différents.
    :func:`archlux.orient.circulaire.stratifier`, elle, centre ses secteurs et nomme
    ``N, NE, …`` : les deux découpages ne sont **pas** interchangeables. Ici seule la
    partition importe (couverture par strate), pas le nom du secteur.
    """
    if n_secteurs < 2:
        raise InvariantViole(("n_secteurs doit être ≥ 2",))
    angles = np.asarray(degres, dtype=float).ravel() % 360.0
    largeur = 360.0 / float(n_secteurs)
    bacs = np.floor(angles / largeur).astype(int)
    bacs = np.clip(bacs, 0, n_secteurs - 1)
    return {k: np.flatnonzero(bacs == k) for k in range(n_secteurs)}


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Empirical coverage of conformal intervals on a sample, and how wide they are.

    Attributes
    ----------
    n : int
        Sample size.
    coverage : float
        Share of truths inside ``[borne_inf, borne_sup]``.
    mean_width : float
        Mean interval width, in the unit of the indicator.
    target_std : float
        Standard deviation of the truths (``ddof=1``): an interval wider than this says
        less than "somewhere in the usual range" (PLAN.md phase 2, J5).
    """

    n: int
    coverage: float
    mean_width: float
    target_std: float

    @property
    def width_over_std(self) -> float:
        """Mean width in units of the target spread; ``inf`` for a constant target."""
        return self.mean_width / self.target_std if self.target_std > 0.0 else math.inf


def measure_coverage(
    calibrator: CalibrateurConforme,
    predictions: np.ndarray,
    truths: np.ndarray,
    uncertainties: np.ndarray,
    *,
    regime: Regime,
) -> CoverageReport:
    """Bound every prediction and count the truths inside (AUDIT.md M12).

    Parameters
    ----------
    calibrator : CalibrateurConforme
        Fitted calibrator.
    predictions, truths, uncertainties : numpy.ndarray
        ``mu``, the oracle value and ``sigma``, point by point (the order of
        :meth:`CalibrateurConforme.ajuster`), on a sample **never used for calibration**.
    regime : {"exchangeable", "selected"}
        Regime of the sample: ``"selected"`` when an optimizer chose the plans.

    Returns
    -------
    CoverageReport

    Raises
    ------
    InvariantViole
        Arrays of different lengths, or fewer than two points.
    """
    mu, sigma, y = (
        np.asarray(a, dtype=float).ravel() for a in (predictions, uncertainties, truths)
    )
    if not mu.size == sigma.size == y.size or mu.size < 2:
        raise InvariantViole((f"need >= 2 aligned points, got {mu.size}, {sigma.size}, {y.size}",))
    bounds = [
        calibrator.borne(float(m), float(s), regime=regime) for m, s in zip(mu, sigma, strict=True)
    ]
    inside = [b.borne_inf <= t <= b.borne_sup for b, t in zip(bounds, y, strict=True)]
    return CoverageReport(
        n=int(mu.size),
        coverage=float(np.mean(inside)),
        mean_width=float(np.mean([b.borne_sup - b.borne_inf for b in bounds])),
        target_std=float(np.std(y, ddof=1)),
    )
