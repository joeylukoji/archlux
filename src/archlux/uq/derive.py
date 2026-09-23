"""Contrôle de dérive : dire quand la garantie conforme cesse de s'appliquer.

L'échangeabilité avec le jeu de calibration n'est pas une propriété permanente. Un
corpus de plans issu d'un nouveau générateur peut sortir du domaine calibré ; la borne
reste alors calculable, mais elle ne garantit plus rien. Ce module le détecte et le dit.

``uq`` n'importe ni ``light`` ni ``solve`` : :func:`mesurer_derive` travaille sur des
tableaux déjà évalués.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import ks_2samp, linregress

from archlux.erreurs import InvariantViole
from archlux.uq.conforme import Calibration

__all__ = [
    "DiagnosticDerive",
    "RapportDerive",
    "controler_derive",
    "mesurer_derive",
]

_SEUIL_P = 0.05
_N_PERMUTATIONS = 199


@dataclass(frozen=True, slots=True)
class DiagnosticDerive:
    """Verdict d'échangeabilité, avec sa statistique et son seuil."""

    echangeable: bool
    statistique: float
    seuil: float
    n_observations: int
    message: str


@dataclass(frozen=True, slots=True)
class RapportDerive:
    """Écart prédiction − vérité sur des plans **sélectionnés**, pas sur la calibration.

    Une dérive positive croissante signifie que l'optimiseur exploite les erreurs du
    substitut. Ce n'est pas une couverture conforme : l'échangeabilité y est douteuse.
    """

    derive_moyenne: float
    tendance_pente: float
    tendance_pvalue: float
    n_echantillons: int


def controler_derive(
    observations: np.ndarray, calibration: Calibration, *, seed: int
) -> DiagnosticDerive:
    """Tester l'échangeabilité des observations avec le jeu de calibration.

    Parameters
    ----------
    observations : numpy.ndarray
        Scores de non-conformité observés en production.
    calibration : Calibration
        Référence.
    seed : int
        Graine du test de permutation. **Obligatoire, sans défaut.**

    Returns
    -------
    DiagnosticDerive
        Verdict lisible. Une dérive détectée **invalide la borne**, elle ne l'élargit
        pas : le certificat doit alors porter ``NON EVALUABLE``, jamais un intervalle.

    Notes
    -----
    Ce que le test garantit, et ce qu'il ne garantit pas :

    - **Niveau exact.** Le p de Monte-Carlo ``(dépassements + 1) / (B + 1)`` avec
      ``B = 199`` (Phipson & Smyth, 2010) est valide à distance finie ; comme
      ``0,05 × 200 = 10`` est entier, rejeter à ``p ≤ 0,05`` donne un niveau
      exactement 5 % sous l'hypothèse nulle d'échangeabilité.
    - **Aucune correction de multiplicité.** Chaque appel est un test indépendant.
      Un contrôle exécuté à chaque lot dérivera vers un faux positif quasi certain
      (``1 − 0,95^k``). Une surveillance continue doit passer par un test séquentiel
      (e-value, mélange conforme martingale) ou au minimum un seuil corrigé.
    - **Puissance non caractérisée.** Aucune analyse de puissance n'accompagne le
      seuil : pour ``n_observations`` petit, ``echangeable=True`` signifie « dérive
      non détectée », pas « pas de dérive ». :func:`archlux.certify.borne.construire_borne`
      traite pourtant ce booléen comme une autorisation de publier.
    - **Statistique mal ciblée.** Kolmogorov-Smirnov est le plus sensible au centre de
      la distribution, alors que la couverture conforme ne dépend que de la **queue
      haute** des scores, au voisinage de ``q̂``. Une dérive qui n'épaissit que cette
      queue est précisément celle qui casse la couverture, et celle que KS voit le
      moins bien. Un test dédié à la queue (ou directement un suivi de
      ``mean(score > q̂)``) serait mieux aligné sur la garantie protégée.
    """
    obs = np.asarray(observations, dtype=float).ravel()
    cal = np.asarray(calibration.scores, dtype=float).ravel()
    if obs.size == 0 or cal.size == 0:
        raise InvariantViole(("observations et calibration doivent être non vides",))
    if not bool(np.all(np.isfinite(obs))) or not bool(np.all(np.isfinite(cal))):
        raise InvariantViole(("scores non finis pour le contrôle de dérive",))
    # Kolmogorov-Smirnov (pas un test de moyennes) : une derive de variance
    # rompt aussi l'echangeabilite, meme a moyenne inchangee.
    statistique = float(ks_2samp(obs, cal).statistic)
    rng = np.random.default_rng(seed)
    pooled = np.concatenate([obs, cal])
    n_obs = int(obs.size)
    depassements = 0
    for _ in range(_N_PERMUTATIONS):
        rng.shuffle(pooled)
        permute = float(ks_2samp(pooled[:n_obs], pooled[n_obs:]).statistic)
        if permute >= statistique:
            depassements += 1
    p_valeur = (depassements + 1) / (_N_PERMUTATIONS + 1)
    echangeable = p_valeur > _SEUIL_P
    if echangeable:
        message = "échangeabilité tenable : la borne conforme reste interprétable"
    else:
        message = (
            "dérive détectée : l'échangeabilité est rejetée, "
            "la borne n'est plus garantie (NON EVALUABLE)"
        )
    return DiagnosticDerive(
        echangeable=echangeable,
        statistique=statistique,
        seuil=_SEUIL_P,
        n_observations=n_obs,
        message=message,
    )


def mesurer_derive(
    predictions: np.ndarray, verites: np.ndarray, *, seed: int
) -> RapportDerive:
    """Écart moyen prédiction − vérité, et tendance sur l'ordre d'arrivée.

    Parameters
    ----------
    predictions, verites : numpy.ndarray
        Évaluations déjà calculées (substitut et oracle gelé), même longueur.
    seed : int
        Conservé pour la signature reproductible ; la régression est déterministe.

    Returns
    -------
    RapportDerive
        ``derive_moyenne`` positive : le substitut surestime l'oracle.

    Notes
    -----
    ``tendance_pvalue`` vient d'une régression des moindres carrés sur l'indice
    d'arrivée : elle suppose des écarts **indépendants et homoscédastiques**. Sur une
    séquence produite par un optimiseur qui réutilise ses itérés, les écarts sont
    autocorrélés et cette p-valeur est anti-conservatrice. À lire comme un indicateur
    de tendance, jamais comme un test formel.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    verite = np.asarray(verites, dtype=float).ravel()
    if pred.size != verite.size or pred.size == 0:
        raise InvariantViole(("predictions et verites de longueurs incompatibles",))
    _ = int(seed)
    ecarts = pred - verite
    n = int(ecarts.size)
    if n >= 3:
        tendance = linregress(np.arange(n, dtype=float), ecarts)
        pente = float(tendance.slope)
        p_valeur = float(tendance.pvalue)
    else:
        pente, p_valeur = 0.0, 1.0
    return RapportDerive(
        derive_moyenne=float(ecarts.mean()),
        tendance_pente=pente,
        tendance_pvalue=p_valeur,
        n_echantillons=n,
    )
