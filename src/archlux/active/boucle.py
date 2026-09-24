"""Boucle actif : sélectionner → simuler → réentraîner → recalibrer.

Le point délicat est la **séparation entraînement / calibration**. Un point simulé
par la boucle ne peut pas servir aux deux : `ARCHITECTURE.md` §10 en fait la seule
erreur silencieuse capable d'invalider une publication. Deux modes en découlent :

- ``run(..., calibration=...)`` — jeu **indépendant**, tiré hors de la boucle. Seul
  mode dont la couverture soit publiable ;
- à défaut, une fraction ``part_calibration`` des points acquis est réservée et
  n'entre jamais dans ``ajuster``. La séparation est tenue, mais les points restent
  *sélectionnés* par l'acquisition : ``RapportActif.calibration_independante`` vaut
  alors ``False``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import structlog

from archlux.active.densite import densite_noyau
from archlux.active.selection import StrategieAcquisition
from archlux.erreurs import InvariantViole
from archlux.uq.conforme import CalibrateurConforme, n_minimal_conforme

if TYPE_CHECKING:
    from archlux.light.protocole import Substitut
    from archlux.types import Orientation

__all__ = ["Loop", "RapportActif"]

_LOG = structlog.get_logger("archlux.active.boucle")


@dataclass(frozen=True, slots=True)
class RapportActif:
    """Résultat d'une campagne à budget de simulations fixé.

    Attributes
    ----------
    calibration_independante : bool
        Vrai si la calibration vient d'un jeu tiré **hors** de la boucle. Faux si
        elle a été prélevée sur les points acquis : les points sont alors choisis
        par la stratégie d'acquisition, donc non échangeables avec un plan de test
        tiré au hasard, et la couverture associée **ne se publie pas**.
    """

    n_simulations: int
    largeur_intervalle_finale: float
    q_final: float
    n_calibration: int
    historique_largeur: tuple[float, ...]
    calibration_independante: bool = False


def _empiler(xs: list[np.ndarray]) -> np.ndarray:
    """Empiler des vecteurs de plan en une matrice ``(n, d)``."""
    return np.stack([np.asarray(x, dtype=float).ravel() for x in xs])


def _incertitudes_acquisition(
    substitut: Substitut,
    xs: list[np.ndarray],
    orientations: list[Orientation],
    xs_labeled: list[np.ndarray],
) -> np.ndarray:
    """σ̂ du substitut × (1 + distance au plus proche déjà simulé).

    Un ``incertitude`` constant (ex. ``SubstitutDense``) ne discrimine pas : la
    distance aux points déjà labellisés force l'exploration.
    """
    base = np.array(
        [float(substitut.incertitude(x, o)) for x, o in zip(xs, orientations, strict=True)],
        dtype=float,
    )
    if not xs_labeled:
        return np.asarray(np.maximum(base, 1e-12), dtype=float)
    ref = _empiler(xs_labeled)
    cand = _empiler(xs)
    dist2 = np.sum((cand[:, None, :] - ref[None, :, :]) ** 2, axis=2)
    dist = np.sqrt(np.min(dist2, axis=1))
    echelle = float(np.median(dist) + 1e-9)
    return np.asarray(np.maximum(base, 1e-12) * (1.0 + dist / echelle), dtype=float)


def _largeur_moyenne(
    calibrateur: CalibrateurConforme,
    substitut: Substitut,
    xs: list[np.ndarray],
    orientations: list[Orientation],
) -> float:
    """Largeur moyenne des intervalles conformes sur le jeu de retenue."""
    largeurs: list[float] = []
    for x, o in zip(xs, orientations, strict=True):
        pred = float(substitut.evaluer(x, o))
        sigma = float(substitut.incertitude(x, o))
        # Held-out plans, never chosen by an optimizer: exchangeable by construction.
        borne = calibrateur.borne(pred, sigma, regime="exchangeable")
        largeurs.append(float(borne.borne_sup - borne.borne_inf))
    return float(np.mean(largeurs))


@dataclass(slots=True)
class Loop:
    """Campagne d'acquisition à budget de simulations.

    Parameters
    ----------
    substitut : Substitut
        Modèle à améliorer. S'il expose ``ajuster``, il est réentraîné chaque cycle.
    simulateur : Substitut
        Oracle gelé (ex. ``OracleSplitFlux``).
    acquire : StrategieAcquisition
        ``UncertaintyTimesDensity`` ou ``Aleatoire``.
    budget : int
        Nombre total d'évaluations oracle **consommées par l'acquisition**. La
        simulation d'un jeu ``calibration=`` indépendant est comptée à part.
    batch : int, optional
        Taille de lot par cycle d'acquisition.
    seed : int
        Graine racine de la campagne. **Obligatoire, sans défaut** et nommée
        (`ARCHITECTURE.md` §7) : ``Loop`` échantillonne (``Aleatoire``, ``ajuster``,
        répartition entraînement / calibration), et un défaut ``17`` laissait passer
        des campagnes silencieusement non rejouables.
    alpha : float, optional
        Niveau conforme visé (défaut 0,10 → couverture 90 %). Fixe aussi la taille
        minimale de calibration, via :func:`~archlux.uq.conforme.n_minimal_conforme`.
    part_calibration : float, optional
        Fraction des points acquis réservée à la calibration quand aucun jeu
        indépendant n'est fourni. ``0.0`` désactive le prélèvement — il faut alors
        passer ``calibration=``, sinon ``run`` lève.

    Warnings
    --------
    Sans ``calibration=``, les points de calibration sont **choisis par la stratégie
    d'acquisition**. Ils sont bien disjoints de ceux vus par ``ajuster`` — la faute
    du §10 est écartée — mais ils ne sont pas échangeables avec un plan de test tiré
    au hasard. Dans ce mode, ``run`` mesure une **largeur d'intervalle**, grandeur
    légitime pour comparer deux stratégies à budget égal, et **pas** une couverture.
    ``RapportActif.calibration_independante`` porte la distinction.
    """

    substitut: Substitut
    simulateur: Substitut
    acquire: StrategieAcquisition
    budget: int
    batch: int = 5
    seed: int = field(kw_only=True)
    alpha: float = field(default=0.10, kw_only=True)
    part_calibration: float = field(default=0.30, kw_only=True)

    def __post_init__(self) -> None:
        """Valider budget, taille de lot, niveau et part de calibration."""
        if self.budget < 1:
            raise InvariantViole(("budget doit être ≥ 1",))
        if self.batch < 1:
            raise InvariantViole(("batch doit être ≥ 1",))
        if not 0.0 < self.alpha < 1.0:
            raise InvariantViole((f"alpha hors ]0, 1[ : {self.alpha}",))
        if not 0.0 <= self.part_calibration < 1.0:
            raise InvariantViole((f"part_calibration hors [0, 1[ : {self.part_calibration}",))

    def _calibrer(
        self,
        calibrateur: CalibrateurConforme,
        xs: list[np.ndarray],
        ys: list[float],
        orientations: list[Orientation],
    ) -> None:
        """Ajuster le quantile conforme sur le jeu de calibration, et lui seul."""
        preds = np.array(
            [float(self.substitut.evaluer(x, o)) for x, o in zip(xs, orientations, strict=True)]
        )
        sigmas = np.array(
            [float(self.substitut.incertitude(x, o)) for x, o in zip(xs, orientations, strict=True)]
        )
        calibrateur.ajuster(preds, np.asarray(ys, dtype=float), sigmas, alpha=self.alpha)

    def _repartir(self, n_acquis: int, rng: np.random.Generator, *, independante: bool) -> set[int]:
        """Rangs du lot courant à verser en calibration plutôt qu'en entraînement.

        Le tirage est **interne au lot** : il ne dépend donc pas de l'ordre
        d'acquisition, qui va du plus exploratoire au plus exploitant.
        """
        if independante or self.part_calibration <= 0.0 or n_acquis < 1:
            return set()
        n_cal = min(n_acquis, max(1, round(self.part_calibration * n_acquis)))
        return {int(j) for j in rng.permutation(n_acquis)[:n_cal]}

    def run(
        self,
        propositions: list[np.ndarray],
        orientations: list[Orientation],
        *,
        reference_optimiseur: list[np.ndarray],
        holdout: list[np.ndarray] | None = None,
        holdout_orientations: list[Orientation] | None = None,
        calibration: list[np.ndarray] | None = None,
        calibration_orientations: list[Orientation] | None = None,
    ) -> RapportActif:
        """Exécuter la boucle jusqu'à épuisement du budget.

        Parameters
        ----------
        propositions :
            Pool de candidats (vectorisés).
        orientations :
            Une orientation par candidat.
        reference_optimiseur :
            Plans typiques produits par l'optimiseur — base de la densité.
        holdout, holdout_orientations :
            Jeu pour mesurer la largeur d'intervalle finale. Défaut : les candidats.
        calibration, calibration_orientations :
            Jeu de calibration **indépendant**, simulé une fois au démarrage et
            jamais soumis à ``ajuster``. Seul mode dont la couverture soit publiable.

        Returns
        -------
        RapportActif
            ``calibration_independante`` dit si la couverture associée est publiable.

        Raises
        ------
        InvariantViole
            Entrées incohérentes, ou calibration trop petite pour ``alpha`` : il faut
            ``n ≥ n_minimal_conforme(alpha)``, soit 9 points à 90 % de couverture.
        """
        if len(propositions) != len(orientations):
            raise InvariantViole(("propositions et orientations de longueurs distinctes",))
        if len(propositions) < self.batch:
            raise InvariantViole(("pool plus petit que le batch",))
        if not reference_optimiseur:
            raise InvariantViole(("reference_optimiseur vide",))

        hold_x = holdout if holdout is not None else propositions
        hold_o = holdout_orientations if holdout_orientations is not None else orientations
        if len(hold_x) != len(hold_o):
            raise InvariantViole(("holdout et orientations de longueurs distinctes",))
        if not hold_x:
            raise InvariantViole(("holdout vide",))

        n_min = n_minimal_conforme(self.alpha)
        independante = calibration is not None
        xs_cal: list[np.ndarray] = []
        os_cal: list[Orientation] = []
        if calibration is not None:
            if calibration_orientations is None or len(calibration) != len(
                calibration_orientations
            ):
                raise InvariantViole(
                    ("calibration et calibration_orientations de longueurs distinctes",)
                )
            if len(calibration) < n_min:
                raise InvariantViole(
                    (f"calibration n={len(calibration)} < {n_min} requis pour alpha={self.alpha}",)
                )
            xs_cal = [np.asarray(x, dtype=float).copy() for x in calibration]
            os_cal = list(calibration_orientations)
        # Vérités du jeu indépendant : simulées une fois, hors budget d'acquisition.
        ys_cal: list[float] = [
            float(self.simulateur.evaluer(x, o)) for x, o in zip(xs_cal, os_cal, strict=True)
        ]

        dens = densite_noyau(_empiler(propositions), _empiler(reference_optimiseur))
        xs_lab: list[np.ndarray] = []
        ys_lab: list[float] = []
        os_lab: list[Orientation] = []
        exclus: list[int] = []
        historique: list[float] = []
        restantes = self.budget
        cycle = 0
        calibrateur = CalibrateurConforme(indicateur="sDA")
        rng = np.random.default_rng(self.seed)

        while restantes > 0:
            n_prendre = min(self.batch, restantes, len(propositions) - len(exclus))
            if n_prendre < 1:
                break
            inc = _incertitudes_acquisition(self.substitut, propositions, orientations, xs_lab)
            idxs = self.acquire.selectionner(
                inc,
                dens,
                n=n_prendre,
                seed=self.seed + cycle,
                exclus=np.asarray(exclus, dtype=int) if exclus else None,
            )
            acquis = [int(i) for i in idxs]
            # Répartir AVANT tout ajustement : c'est ce qui empêche matériellement
            # ``ajuster`` de voir un point de calibration.
            vers_calibration = self._repartir(len(acquis), rng, independante=independante)
            for rang, i in enumerate(acquis):
                x = np.asarray(propositions[i], dtype=float).copy()
                o = orientations[i]
                y = float(self.simulateur.evaluer(x, o))
                if rang in vers_calibration:
                    xs_cal.append(x)
                    ys_cal.append(y)
                    os_cal.append(o)
                else:
                    xs_lab.append(x)
                    ys_lab.append(y)
                    os_lab.append(o)
                exclus.append(i)
            restantes -= len(acquis)

            ajuster = getattr(self.substitut, "ajuster", None)
            if ajuster is not None and len(xs_lab) >= 2:
                ajuster(
                    tuple(xs_lab),
                    np.asarray(ys_lab, dtype=float),
                    tuple(os_lab),
                    seed=self.seed + cycle,
                    epoques=40,
                    lr=0.12,
                )

            # Recalibrer après chaque cycle : le modèle a changé, l'ancien q̂ ne borne
            # plus rien. Les scores viennent de ``xs_cal``, jamais de ``xs_lab``.
            if len(xs_cal) >= n_min:
                try:
                    self._calibrer(calibrateur, xs_cal, ys_cal, os_cal)
                    historique.append(_largeur_moyenne(calibrateur, self.substitut, hold_x, hold_o))
                except InvariantViole as echec:
                    # Scores dégénérés en début de campagne : conserver le calibrateur
                    # courant et retenter au cycle suivant. Le rattrapage est tracé —
                    # ``erreurs.InvariantViole`` interdit de l'avaler en silence — et
                    # reste borné : si aucun cycle n'aboutit, ``calibrateur.n < 1`` et
                    # le repli ci-dessous relaie l'échec.
                    _LOG.warning(
                        "calibration_cycle_ignoree",
                        cycle=cycle,
                        n_calibration=len(xs_cal),
                        violations=echec.violations,
                    )
            cycle += 1

        if calibrateur.n < 1:
            if len(xs_cal) < n_min:
                raise InvariantViole(
                    (
                        f"calibration insuffisante : n={len(xs_cal)} < {n_min} pour "
                        f"alpha={self.alpha} ; augmenter budget ou part_calibration, "
                        f"ou passer un jeu calibration= indépendant",
                    )
                )
            self._calibrer(calibrateur, xs_cal, ys_cal, os_cal)
            historique.append(_largeur_moyenne(calibrateur, self.substitut, hold_x, hold_o))

        largeur = historique[-1] if historique else float("nan")
        return RapportActif(
            n_simulations=len(xs_lab) + len(xs_cal),
            largeur_intervalle_finale=largeur,
            q_final=float(calibrateur.q),
            n_calibration=int(calibrateur.n),
            historique_largeur=tuple(historique),
            calibration_independante=independante,
        )
