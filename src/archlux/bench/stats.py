"""Tests statistiques purs du banc (bootstrap, TOST, Holm, puissance)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as scipy_stats

from archlux.erreurs import InvariantViole

__all__ = ["Intervalle", "bootstrap_apparie", "holm", "puissance", "tost"]


@dataclass(frozen=True, slots=True)
class Intervalle:
    """Estimation ponctuelle et bornes d'intervalle."""

    valeur: float
    bas: float
    haut: float


def bootstrap_apparie(
    a: Sequence[float],
    b: Sequence[float],
    *,
    seed: int,
    n_replications: int = 9999,
    alpha: float = 0.05,
) -> Intervalle:
    """Intervalle de confiance bootstrap sur la moyenne des différences appariées."""
    if len(a) != len(b) or len(a) < 1:
        raise InvariantViole(("a et b doivent avoir la même longueur ≥ 1",))
    if n_replications < 1:
        raise InvariantViole(("n_replications doit être ≥ 1",))
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    n = len(diffs)
    echantillon = rng.choice(diffs, size=(n_replications, n), replace=True)
    moyens = echantillon.mean(axis=1)
    lo, hi = np.quantile(moyens, [alpha / 2.0, 1.0 - alpha / 2.0])
    return Intervalle(valeur=float(diffs.mean()), bas=float(lo), haut=float(hi))


def tost(
    a: Sequence[float],
    b: Sequence[float],
    *,
    delta: float,
    alpha: float = 0.05,
) -> tuple[bool, float]:
    """TOST d'équivalence sur la moyenne des différences appariées.

    Returns
    -------
    tuple
        ``(equivalent, p)`` où ``p = max(p_inf, p_sup)``.
    """
    if len(a) != len(b) or len(a) < 2:
        raise InvariantViole(("a et b doivent avoir la même longueur ≥ 2",))
    if delta <= 0.0:
        raise InvariantViole(("delta doit être > 0",))
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(diffs)
    moyenne = float(diffs.mean())
    ecart = float(diffs.std(ddof=1))
    if ecart == 0.0:
        equivalent = abs(moyenne) < delta
        return equivalent, 0.0 if equivalent else 1.0
    se = ecart / np.sqrt(n)
    t_inf = (moyenne - (-delta)) / se
    t_sup = (delta - moyenne) / se
    ddl = n - 1
    p_inf = float(1.0 - scipy_stats.t.cdf(t_inf, ddl))
    p_sup = float(1.0 - scipy_stats.t.cdf(t_sup, ddl))
    p = max(p_inf, p_sup)
    return p < alpha, p


def holm(p_valeurs: Sequence[float], *, alpha: float = 0.05) -> tuple[bool, ...]:
    """Correction de Holm-Bonferroni pour comparaisons multiples.

    Une table d'article compare typiquement plusieurs méthodes sur plusieurs strates
    d'orientation. Sans correction, la probabilité qu'au moins un des ``m`` tests
    ressorte significatif par hasard tend vers 1 : à ``m = 16`` et ``alpha = 0,05``,
    elle vaut déjà ``1 − 0,95¹⁶ ≈ 0,56``. Holm contrôle le taux d'erreur **par
    famille** (FWER) sans hypothèse d'indépendance, contrairement à Benjamini-Hochberg
    qui ne contrôle que le FDR.

    Parameters
    ----------
    p_valeurs : Sequence[float]
        Les ``m`` p-valeurs de la famille, dans ``[0, 1]``.
    alpha : float, optional
        Taux d'erreur par famille visé.

    Returns
    -------
    tuple of bool
        ``rejete[i]`` pour chaque p-valeur, **dans l'ordre d'entrée**.

    Raises
    ------
    InvariantViole
        Famille vide, ``alpha`` hors ``]0, 1[``, ou p-valeur hors ``[0, 1]``.

    Complexity
    ----------
    ``O(m log m)`` (le tri domine).

    Examples
    --------
    >>> from archlux.bench.stats import holm
    >>> holm([0.001, 0.04, 0.6])
    (True, False, False)
    """
    p = np.asarray(p_valeurs, dtype=float)
    if p.size == 0:
        raise InvariantViole(("famille de p-valeurs vide",))
    if not 0.0 < alpha < 1.0:
        raise InvariantViole((f"alpha hors ]0, 1[ : {alpha}",))
    if bool(np.any(p < 0.0) or np.any(p > 1.0)) or bool(np.any(np.isnan(p))):
        raise InvariantViole(("p-valeurs hors [0, 1]",))
    m = p.size
    ordre = np.argsort(p, kind="stable")
    seuils = alpha / (m - np.arange(m))
    sous_seuil = p[ordre] <= seuils
    # Holm s'arrête au **premier** échec : tout ce qui suit est conservé, même si sa
    # p-valeur repasse sous son propre seuil. Le cumul monotone impose cet arrêt.
    rejets_tries = np.logical_and.accumulate(sous_seuil)
    rejets = np.empty(m, dtype=bool)
    rejets[ordre] = rejets_tries
    return tuple(bool(v) for v in rejets)


def puissance(
    effet: float,
    sigma: float,
    *,
    n: int,
    alpha: float = 0.05,
) -> float:
    """Puissance approximative d'un test t bilatéral à un échantillon."""
    if n < 2:
        raise InvariantViole(("n doit être ≥ 2",))
    if sigma <= 0.0:
        raise InvariantViole(("sigma doit être > 0",))
    if not 0.0 < alpha < 1.0:
        raise InvariantViole((f"alpha hors ]0, 1[ : {alpha}",))
    ddl = n - 1
    se = sigma / np.sqrt(n)
    t_crit = float(scipy_stats.t.ppf(1.0 - alpha / 2.0, ddl))
    ncp = effet / se
    # Puissance = P(|T| > t_crit | ncp)
    p_bas = float(scipy_stats.nct.cdf(-t_crit, ddl, ncp))
    p_haut = float(1.0 - scipy_stats.nct.cdf(t_crit, ddl, ncp))
    return float(np.clip(p_bas + p_haut, 0.0, 1.0))
