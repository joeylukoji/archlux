"""Prédiction conforme : transformer une estimation en intervalle à couverture garantie.

**Le quantile n'est pas ``numpy.quantile``.** La couverture à échantillon fini exige
l'indice ``ceil((n + 1)(1 − α))`` sur les scores triés. Utiliser le quantile empirique
ordinaire donne des intervalles trop étroits, donc une couverture inférieure à celle qui
est annoncée — et rien ne le signale (`ARCHITECTURE.md` §10).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.types import BornePerformance

__all__ = [
    "CalibrateurConforme",
    "Calibration",
    "borner",
    "n_minimal_conforme",
    "quantile_conforme",
]

_Indicateur = Literal["sDA", "ASE", "UDI", "vue"]
_SIGMA_MIN = 1e-12


@dataclass(frozen=True, slots=True)
class Calibration:
    """Scores de non-conformité issus du jeu de calibration, et rien d'autre.

    Attributes
    ----------
    empreinte_jeu : str
        ``sha256`` du jeu utilisé. Publié avec le modèle : une borne conforme dont le
        jeu de calibration n'est pas publiable est une garantie invérifiable.
    """

    scores: np.ndarray
    alpha: float
    indicateur: str
    empreinte_jeu: str

    @property
    def n(self) -> int:
        """Taille du jeu de calibration."""
        return int(self.scores.size)


def n_minimal_conforme(alpha: float) -> int:
    r"""Plus petite taille de calibration permettant une borne finie au niveau ``alpha``.

    Le quantile conforme prend le rang ``k = ceil((n + 1)(1 - alpha))``. Il faut
    ``k <= n``, sinon le score demande sort de l'echantillon et la borne serait
    infinie. Comme ``n`` est entier, ``ceil(x) <= n`` equivaut a ``x <= n``, d'ou

    .. math::

        (n + 1)(1 - \alpha) \le n
        \iff n \ge \frac{1}{\alpha} - 1 .

    A 90 % de couverture il faut donc ``n >= 9``, et a 95 % ``n >= 19``. Un jeu de
    calibration plus petit ne rend pas la garantie fausse : il la rend **impossible**,
    et :func:`quantile_conforme` leve plutot que de publier une borne infinie.

    Parameters
    ----------
    alpha : float
        Niveau vise, dans ``]0, 1[``. La couverture garantie est ``>= 1 - alpha``.

    Returns
    -------
    int
        Le plus petit ``n`` admissible.

    Raises
    ------
    InvariantViole
        Si ``alpha`` sort de ``]0, 1[``.

    Examples
    --------
    >>> from archlux.uq.conforme import n_minimal_conforme
    >>> n_minimal_conforme(0.10), n_minimal_conforme(0.05)
    (9, 19)
    """
    if not 0.0 < alpha < 1.0:
        raise InvariantViole((f"alpha hors ]0, 1[ : {alpha}",))
    # Recherche entiere plutot que ceil(1/alpha - 1) : en flottant, 1/0.1 vaut
    # 10.000000000000002 et l'arrondi rendrait 10 au lieu de 9.
    n = max(1, int(1.0 / alpha) - 2)
    while math.ceil((n + 1) * (1.0 - alpha)) > n:
        n += 1
    return n


def quantile_conforme(scores: np.ndarray, alpha: float) -> float:
    """Quantile conforme corrigé pour l'échantillon fini.

    Parameters
    ----------
    scores : numpy.ndarray
        Scores de non-conformité, un par point de calibration.
    alpha : float
        Niveau visé ; la couverture garantie est ``≥ 1 − alpha``.

    Returns
    -------
    float
        Le score de rang ``ceil((n + 1)(1 − alpha))`` dans l'ordre croissant.

    Raises
    ------
    InvariantViole
        Si ``ceil((n + 1)(1 − alpha)) > n`` : le jeu de calibration est trop petit pour
        le niveau demandé. Échec explicite plutôt que borne infinie silencieuse.

    Notes
    -----
    La garantie est **bilatérale** sous échangeabilité et scores continus :
    ``1 − alpha ≤ P(score ≤ q̂) ≤ 1 − alpha + 1/(n + 1)``. Elle est donc *marginale*
    (moyennée sur le tirage du jeu de calibration), jamais conditionnelle au plan.

    Les **ex-aequo** ne cassent rien : le rang est pris sur l'ordre croissant, si bien
    qu'un paquet de scores égaux ne peut que faire monter ``q̂``. La couverture reste
    ``≥ 1 − alpha`` ; seule la borne supérieure ``+ 1/(n + 1)`` cesse de tenir, et
    l'intervalle devient conservateur. Aucune départie aléatoire n'est appliquée.
    """
    vecteur = np.asarray(scores, dtype=float).ravel()
    n = int(vecteur.size)
    if n == 0:
        raise InvariantViole(("jeu de calibration vide",))
    if not bool(np.all(np.isfinite(vecteur))):
        raise InvariantViole(("scores de calibration non finis",))
    if not 0.0 < alpha < 1.0:
        raise InvariantViole((f"alpha hors ]0, 1[ : {alpha}",))
    rang = math.ceil((n + 1) * (1.0 - alpha))
    if rang > n:
        raise InvariantViole((f"n={n} trop petit pour alpha={alpha} (rang {rang} > n)",))
    ordre = np.sort(vecteur)
    return float(ordre[rang - 1])


def _indicateur(nom: str) -> _Indicateur:
    if nom not in ("sDA", "ASE", "UDI", "vue"):
        raise InvariantViole((f"indicateur inconnu : {nom!r}",))
    return nom  # type: ignore[return-value]


def _empreinte_scores(scores: np.ndarray) -> str:
    tampon = np.ascontiguousarray(scores, dtype=float).tobytes()
    return hashlib.sha256(tampon).hexdigest()


def _echelle(incertitude: float) -> float:
    """Valider ``σ̂`` avant d'en faire une marge conforme.

    Les scores sont normalisés (``|y − ŷ| / σ``) : la marge publiée n'a de sens que
    si ``σ̂`` est fini et **strictement positif**. Sans ce contrôle, ``σ̂ = 0`` publie
    un intervalle de largeur nulle en annonçant une couverture de ``1 − α``, et
    ``σ̂ < 0`` publie un intervalle inversé (``borne_inf > borne_sup``) — deux
    garanties fausses que rien ne signalerait.

    Raises
    ------
    InvariantViole
        Si ``incertitude`` n'est pas finie ou n'est pas ``> 0``.
    """
    echelle = float(incertitude)
    if not math.isfinite(echelle):
        raise InvariantViole((f"incertitude non finie : {incertitude}",))
    if echelle <= 0.0:
        raise InvariantViole(
            (
                f"incertitude doit être > 0 pour publier une marge conforme : {echelle}",
            )
        )
    return max(echelle, _SIGMA_MIN)


def _intervalle(
    prediction: float,
    marge: float,
    *,
    indicateur: _Indicateur,
    couverture: float,
    n_calibration: int,
) -> BornePerformance:
    """Intervalle bilatéral ``prédiction ± marge`` ; le sens métier est le côté publié."""
    return BornePerformance(
        indicateur=indicateur,
        valeur=float(prediction),
        borne_inf=float(prediction) - marge,
        borne_sup=float(prediction) + marge,
        couverture=couverture,
        n_calibration=n_calibration,
    )


def borner(
    valeur: float, calibration: Calibration, *, incertitude: float = 1.0
) -> BornePerformance:
    """Assortir une estimation ponctuelle de son intervalle conforme.

    Parameters
    ----------
    valeur : float
        Estimation ponctuelle (même unité que l'indicateur).
    calibration : Calibration
        Scores de non-conformité. S'ils sont déjà normalisés par ``σ``, passer
        ``incertitude`` égale à ``σ`` du point à borner.
    incertitude : float, optional
        Échelle locale, **strictement positive**. Défaut 1 : les scores sont alors
        dans l'unité de ``valeur``. Ce défaut n'est correct que pour une calibration
        **non normalisée** : si les scores viennent de
        :meth:`CalibrateurConforme.ajuster` (donc divisés par ``σ``), laisser le défaut
        publie une marge à la mauvaise échelle.

    Raises
    ------
    InvariantViole
        Si ``incertitude`` n'est pas finie ou n'est pas ``> 0``.

    Guarantees
    ----------
    - Performance : **probabiliste**, couverture ``≥ 1 − alpha`` sous hypothèse
      d'échangeabilité avec le jeu de calibration. ``BornePerformance.couverture``
      porte le niveau **nominal** ``1 − alpha``, jamais une couverture mesurée.
      Cette hypothèse est **affaiblie** lorsque le plan a été sélectionné par
      l'optimiseur pour maximiser la prédiction ; le projet mesure et publie la
      couverture réelle sous sélection.
    """
    q_chapeau = quantile_conforme(calibration.scores, calibration.alpha)
    marge = q_chapeau * _echelle(incertitude)
    return _intervalle(
        valeur,
        marge,
        indicateur=_indicateur(calibration.indicateur),
        couverture=1.0 - calibration.alpha,
        n_calibration=calibration.n,
    )


@dataclass(slots=True)
class CalibrateurConforme:
    """Un calibrateur par indicateur : les erreurs de sDA et d'ASE n'ont pas la même échelle.

    ``ajuster`` lit le jeu de calibration **après** gel du modèle. ``q``, ``n`` et
    ``alpha`` se sérialisent avec les poids.
    """

    indicateur: _Indicateur = "sDA"
    q: float = 0.0
    n: int = 0
    alpha: float = 0.10
    empreinte_jeu: str = ""
    scores: np.ndarray | None = field(default=None, repr=False, compare=False)

    def ajuster(
        self,
        predictions: np.ndarray,
        verites: np.ndarray,
        incertitudes: np.ndarray,
        *,
        alpha: float = 0.10,
    ) -> None:
        """Ajuster le quantile sur des scores normalisés ``|y − ŷ| / σ``.

        Parameters
        ----------
        predictions, verites, incertitudes : numpy.ndarray
            Un scalaire par plan, même longueur.
        alpha : float, optional
            Niveau visé (défaut 0,10 → couverture 90 %).
        """
        pred = np.asarray(predictions, dtype=float).ravel()
        verite = np.asarray(verites, dtype=float).ravel()
        sigma = np.maximum(np.asarray(incertitudes, dtype=float).ravel(), _SIGMA_MIN)
        if pred.size != verite.size or pred.size != sigma.size:
            raise InvariantViole(("predictions, verites et incertitudes de longueurs distinctes",))
        if pred.size == 0:
            raise InvariantViole(("jeu de calibration vide",))
        scores = np.abs(verite - pred) / sigma
        self.q = quantile_conforme(scores, alpha)
        self.n = int(scores.size)
        self.alpha = float(alpha)
        self.empreinte_jeu = _empreinte_scores(scores)
        self.scores = np.array(scores, dtype=float, copy=True)

    def borne(
        self, prediction: float, incertitude: float, sens: str | None = None
    ) -> BornePerformance:
        """Publier l'intervalle conforme autour de ``prediction``.

        Parameters
        ----------
        prediction : float
            Estimation ponctuelle.
        incertitude : float
            ``σ̂`` au même point, **strictement positif** : les scores ajustés sont
            normalisés, donc ``σ̂ = 0`` publierait un intervalle de largeur nulle
            annoncé à ``1 − α``, et ``σ̂ < 0`` un intervalle inversé.
        sens : {">=", "<=", None}
            Doit coller à l'indicateur (``"<="`` pour ASE, ``">="`` sinon).
            Défaut : déduit de ``indicateur``. L'intervalle publié reste bilatéral
            ``prédiction ± marge`` ; le rapport choisit le côté via ``indicateur``.
            ``sens`` ne change pas les bornes — il refuse seulement l'incohérence.
        """
        if self.n < 1:
            raise InvariantViole(("calibrateur non ajusté",))
        attendu = "<=" if self.indicateur == "ASE" else ">="
        if sens is None:
            sens = attendu
        if sens not in (">=", "<="):
            raise InvariantViole((f"sens inconnu : {sens!r}",))
        if sens != attendu:
            raise InvariantViole(
                (f"sens {sens!r} incompatible avec indicateur {self.indicateur}",)
            )
        marge = self.q * _echelle(incertitude)
        return _intervalle(
            prediction,
            marge,
            indicateur=self.indicateur,
            couverture=1.0 - self.alpha,
            n_calibration=self.n,
        )

    def snapshot(self) -> Calibration:
        """Geler les scores et ``alpha`` pour ``borner`` / le certificat.

        ``borner`` recalcule le quantile conforme à partir des scores ; l'empreinte
        du jeu reste journalisée avec la calibration.
        """
        if self.n < 1 or self.scores is None:
            raise InvariantViole(("calibrateur non ajusté",))
        return Calibration(
            scores=np.array(self.scores, dtype=float, copy=True),
            alpha=self.alpha,
            indicateur=self.indicateur,
            empreinte_jeu=self.empreinte_jeu,
        )
