"""Perceptron sur descripteurs — valide la chaîne d'apprentissage sans ``torch``.

Un réseau dense à trois couches se code en une journée et **exerce** chargeurs,
normalisation, journalisation. Si le gradient est déjà faux ici, c'est la
tokenisation qui est en cause, pas le transformeur (`MILESTONE-4.md` §4).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.jetons import vecteur_vers_jetons
from archlux.light.protocole import Baies
from archlux.orient.circulaire import encode
from archlux.types import Orientation

__all__ = ["SubstitutDense", "descripteurs"]

_EPS = 1e-8

FRACTION_SIGMA_RESIDUEL = 0.15
"""Part de ``sigma_y`` retenue comme sigma predictif apres entrainement.

**Constante non justifiee par une mesure.** Elle postule que le reseau absorbe 85 %
de l'ecart-type du residu a l'analytique, ce qui n'est verifie nulle part. Elle ne peut
ni casser ni fonder la couverture conforme : celle-ci reste au moins 1 moins alpha pour
*n'importe quel* sigma strictement positif, puisque la calibration divise par le meme
sigma. Elle n'agit que sur l'**adaptativite** de la largeur d'intervalle. Avant
publication, la remplacer par un sigma estime sur un jeu de validation disjoint (residu
absolu regresse sur les descripteurs, ou regression quantile), pas par un scalaire
choisi a la main.
"""

SIGMA_PLANCHER = 0.02
"""Plancher du sigma predictif, en unite de l'indicateur. Meme statut : valeur d'atelier.
"""


@lru_cache(maxsize=len(("sDA", "ASE", "UDI", "vue")))
def _analytique(indicateur: Literal["sDA", "ASE", "UDI", "vue"]) -> SubstitutAnalytique:
    """Instance analytique partagée : gelée, sans état, réutilisable sans copie.

    :meth:`SubstitutDense.gradient` évalue ``2 n`` fois par gradient ; reconstruire le
    substitut à chaque évaluation était du travail pur perte sur le chemin critique du
    §9 d'``ARCHITECTURE.md``.
    """
    return SubstitutAnalytique(indicateur_vise=indicateur)


def descripteurs(x: np.ndarray, orientation: Orientation, baies: Baies | None = None) -> np.ndarray:
    """Descripteurs continus : statistiques de pièces × harmoniques d'orientation.

    Inclut explicitement ``aire × sin 2θ``, terme présent dans le simulateur
    synthétique et absent de l'analytique — sans lui le perceptron ne peut pas
    gagner.
    """
    jetons, masque = vecteur_vers_jetons(x, orientation, baies)
    valides = jetons[~masque]
    # Les jetons de baie portent leur drapeau en colonne 27 ; les separer evite de
    # moyenner des pieces et des fenetres dans un meme vecteur, ce qui n'a pas de
    # sens dimensionnel.
    est_baie = valides[:, 27] > 0.5
    pieces_seules = valides[~est_baie]
    fenetres = valides[est_baie]
    if pieces_seules.size:
        valides = pieces_seules
    if valides.size == 0:
        raise InvariantViole(("vecteur de plan vide : aucun jeton",))
    moyen = valides.mean(axis=0)
    aires = valides[:, 4]
    enc = encode(orientation.deg, harmoniques=3)
    stats = np.array(
        [
            float(valides.shape[0]),
            float(aires.sum()),
            float(valides[:, 2].mean()),
            float(valides[:, 3].mean()),
            float(valides[:, 0].mean()),
            float(valides[:, 1].mean()),
        ],
        dtype=float,
    )
    interaction = np.outer(enc, stats).ravel()
    sin2 = enc[3]
    extra = np.array([float(aires.sum()) * sin2, float(aires.sum()) * enc[2]], dtype=float)
    # Six descripteurs de fenestration, nuls quand aucune baie n'est fournie : le
    # vecteur garde donc la meme dimension, et un modele entraine sans baies reste
    # lisible par un modele qui en recoit.
    if fenetres.size:
        largeurs = fenetres[:, 25]
        baies_stats = np.array(
            [
                float(fenetres.shape[0]),
                float(largeurs.sum()),
                float(largeurs.mean()),
                float(fenetres[:, 26].mean()),
                float(np.mean(fenetres[:, 22])),
                float(np.mean(fenetres[:, 23])),
            ],
            dtype=float,
        )
    else:
        baies_stats = np.zeros(6, dtype=float)
    return np.concatenate([moyen, enc, stats, interaction, extra, baies_stats])


def _huber_derivee(residu: float, delta: float = 1.0) -> float:
    """Dérivée de la perte de Huber, bornée hors de ``[-delta, delta]``."""
    if abs(residu) <= delta:
        return residu
    return delta * (1.0 if residu > 0.0 else -1.0)


@dataclass
class SubstitutDense:
    """Réseau dense 3 couches, poids numpy. Entrée vectorielle uniquement."""

    indicateur_vise: Literal["sDA", "ASE", "UDI", "vue"] = "sDA"
    largeur: int = 32
    W1: np.ndarray | None = None
    b1: np.ndarray | None = None
    W2: np.ndarray | None = None
    b2: np.ndarray | None = None
    W3: np.ndarray | None = None
    b3: float = 0.0
    mu: np.ndarray | None = None
    sigma: np.ndarray | None = None
    mu_y: float = 0.0
    sigma_y: float = 1.0
    echelle_base: float = 1.0
    decalage_base: float = 0.0

    @property
    def indicateur(self) -> str:
        """Nom de l'indicateur modélisé."""
        return self.indicateur_vise

    def n_parametres(self) -> int:
        """Nombre de scalaires entraînés."""
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
        ):
            return 0
        return int(self.W1.size + self.b1.size + self.W2.size + self.b2.size + self.W3.size + 1)

    def _normaliser(self, feat: np.ndarray) -> np.ndarray:
        if self.mu is None or self.sigma is None:
            return feat
        return np.asarray((feat - self.mu) / np.maximum(self.sigma, _EPS), dtype=float)

    def _forward(self, feat: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        """Passe avant. Garde explicite : ``assert`` disparaît sous ``python -O``."""
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
        ):
            raise InvariantViole(("passe avant sur un modèle non entraîné",))
        z1 = feat @ self.W1 + self.b1
        h1 = np.tanh(z1)
        z2 = h1 @ self.W2 + self.b2
        h2 = np.tanh(z2)
        y_hat = float(h2 @ self.W3 + self.b3)
        return y_hat, h1, h2

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Analytique recalée + résidu appris. Sans poids : l'analytique seule."""
        base = (
            self.echelle_base * float(_analytique(self.indicateur_vise).evaluer(x, orientation))
            + self.decalage_base
        )
        if self.W1 is None:
            return base
        feat = self._normaliser(descripteurs(x, orientation, baies))
        y_hat, _, _ = self._forward(feat)
        return base + y_hat * self.sigma_y + self.mu_y

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        """Différences finies centrées sur le vecteur de plan.

        Coût : ``2 n`` appels à :meth:`evaluer` (``n = 4 × pièces``), soit 120 passes
        complètes pour 15 pièces. Sur 50 itérations Frank-Wolfe, c'est l'essentiel du
        budget « légalisation performantielle < 500 ms » (``ARCHITECTURE.md`` §9), et
        cela ne tiendra pas pour un modèle plus lourd. La rétropropagation exacte est
        possible — le réseau est différentiable et l'analytique a un gradient fermé —
        mais elle change les valeurs rendues près du coude
        ``profondeur == profondeur_utile`` : la substituer exige de repasser
        :func:`archlux.light.validation.valider_gradient`.
        """
        x0 = np.asarray(x, dtype=float).ravel().copy()
        g = np.empty_like(x0)
        pas = 1e-4
        for i in range(x0.size):
            plus, moins = x0.copy(), x0.copy()
            plus[i] += pas
            moins[i] -= pas
            g[i] = (
                self.evaluer(plus, orientation, baies=baies)
                - self.evaluer(moins, orientation, baies=baies)
            ) / (2.0 * pas)
        return g

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """``σ̂`` **constant**, dérivé de ``sigma_y`` par une fraction d'atelier.

        Ne dépend ni de ``x`` ni de l'orientation : ce n'est donc pas une incertitude
        prédictive, seulement une échelle. La couverture conforme reste valide (voir
        :data:`FRACTION_SIGMA_RESIDUEL`), mais l'intervalle a partout la même largeur :
        aucun gain d'adaptativité, et le chiffre ``0,15`` n'est adossé à aucune mesure.
        """
        del x, orientation, baies
        return float(max(self.sigma_y * FRACTION_SIGMA_RESIDUEL, SIGMA_PLANCHER))

    def ajuster(
        self,
        xs: tuple[np.ndarray, ...],
        ys: np.ndarray,
        orientations: tuple[Orientation, ...],
        *,
        seed: int,
        epoques: int = 120,
        lr: float = 0.08,
        baies: tuple[Baies | None, ...] | None = None,
    ) -> None:
        """Recaler l'analytique, puis descente de gradient Huber sur le **résidu**.

        Le recalage affine n'est pas cosmétique. ``SubstitutAnalytique`` rend un
        score en **unités arbitraires** — une somme de façades pondérées, de l'ordre
        de la centaine — sans aucune échelle physique. Contre ``SimulateurExact``,
        construit sur la même base, les deux coïncident et le résidu est petit.
        Contre une simulation réelle (Swiss Dwellings, irradiance de l'ordre de 1),
        le résidu vaudrait l'opposé du score : le réseau passerait sa capacité à
        annuler une constante d'échelle au lieu d'apprendre la physique.

        On ajuste donc d'abord ``y ≈ a·f(x) + b`` par moindres carrés sur le jeu
        d'entraînement, puis le réseau apprend le résidu à cette base **recalée**.
        ``a = 1``, ``b = 0`` restaure exactement le comportement antérieur.
        """
        if len(xs) != len(ys) or len(xs) != len(orientations):
            raise InvariantViole(("xs, ys et orientations doivent avoir la même longueur",))
        analytique = _analytique(self.indicateur_vise)
        brut = np.array(
            [float(analytique.evaluer(x, ori)) for x, ori in zip(xs, orientations, strict=True)]
        )
        cible_brute = np.asarray(ys, dtype=float).ravel()
        variance = float(np.var(brut))
        if variance > _EPS:
            pente, ordonnee = np.polyfit(brut, cible_brute, 1)
            self.echelle_base = float(pente)
            self.decalage_base = float(ordonnee)
        else:
            self.echelle_base = 0.0
            self.decalage_base = float(np.mean(cible_brute))
        residus = cible_brute - (self.echelle_base * brut + self.decalage_base)
        fenestration = baies if baies is not None else (None,) * len(xs)
        feats = np.stack(
            [descripteurs(x, o, b) for x, o, b in zip(xs, orientations, fenestration, strict=True)]
        )
        self.mu = feats.mean(axis=0)
        self.sigma = feats.std(axis=0)
        self.sigma[self.sigma < _EPS] = 1.0
        feats = (feats - self.mu) / self.sigma
        self.mu_y = float(np.mean(residus))
        self.sigma_y = max(float(np.std(residus)), _EPS)
        cibles = (residus - self.mu_y) / self.sigma_y
        rng = np.random.default_rng(seed)
        dim = int(feats.shape[1])
        k = self.largeur
        self.W1 = rng.normal(0.0, 1.0 / math.sqrt(dim), size=(dim, k))
        self.b1 = np.zeros(k)
        self.W2 = rng.normal(0.0, 1.0 / math.sqrt(k), size=(k, k))
        self.b2 = np.zeros(k)
        self.W3 = rng.normal(0.0, 1.0 / math.sqrt(k), size=(k,))
        self.b3 = 0.0
        n = feats.shape[0]
        for _ in range(epoques):
            ordre = rng.permutation(n)
            for indice in ordre:
                feat = feats[indice]
                y_hat, h1, h2 = self._forward(feat)
                residu = y_hat - float(cibles[indice])
                d_y = _huber_derivee(residu)
                d_h2 = d_y * self.W3 * (1.0 - h2 * h2)
                d_h1 = (d_h2 @ self.W2.T) * (1.0 - h1 * h1)
                self.W3 -= lr * d_y * h2
                self.b3 -= lr * d_y
                self.W2 -= lr * np.outer(h1, d_h2)
                self.b2 -= lr * d_h2
                self.W1 -= lr * np.outer(feat, d_h1)
                self.b1 -= lr * d_h1

    def sauver(self, chemin: Path) -> str:
        """Écrire les poids en ``npz``. Rend l'empreinte SHA-256 du fichier **écrit**.

        ``numpy.savez`` ajoute lui-même ``.npz`` quand le chemin n'en porte pas ; le
        suffixe est donc normalisé ici, sinon l'empreinte serait calculée sur un
        fichier inexistant. Rendre le chemin réellement écrit n'est pas nécessaire :
        il se déduit par la même règle.
        """
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
            or self.mu is None
            or self.sigma is None
        ):
            raise InvariantViole(("sauver un modèle non entraîné",))
        chemin = Path(chemin)
        if chemin.suffix != ".npz":
            chemin = chemin.with_name(chemin.name + ".npz")
        np.savez(
            chemin,
            W1=self.W1,
            b1=self.b1,
            W2=self.W2,
            b2=self.b2,
            W3=self.W3,
            b3=np.array(self.b3),
            mu=self.mu,
            sigma=self.sigma,
            mu_y=np.array(self.mu_y),
            sigma_y=np.array(self.sigma_y),
            echelle_base=np.array(self.echelle_base),
            decalage_base=np.array(self.decalage_base),
            indicateur=np.array(self.indicateur_vise),
        )
        return hashlib.sha256(chemin.read_bytes()).hexdigest()

    @classmethod
    def charger(cls, chemin: Path) -> SubstitutDense:
        """Relire un ``npz`` produit par :meth:`sauver`."""
        indicateurs: tuple[Literal["sDA", "ASE", "UDI", "vue"], ...] = (
            "sDA",
            "ASE",
            "UDI",
            "vue",
        )
        with np.load(Path(chemin), allow_pickle=False) as archive:
            indicateur = str(archive["indicateur"])
            if indicateur not in indicateurs:
                raise InvariantViole((f"indicateur inconnu dans les poids : {indicateur}",))
            modele = cls(indicateur_vise=cast(Literal["sDA", "ASE", "UDI", "vue"], indicateur))
            modele.W1 = np.array(archive["W1"], dtype=float, copy=True)
            modele.b1 = np.array(archive["b1"], dtype=float, copy=True)
            modele.W2 = np.array(archive["W2"], dtype=float, copy=True)
            modele.b2 = np.array(archive["b2"], dtype=float, copy=True)
            modele.W3 = np.array(archive["W3"], dtype=float, copy=True)
            modele.b3 = float(archive["b3"])
            modele.mu = np.array(archive["mu"], dtype=float, copy=True)
            modele.sigma = np.array(archive["sigma"], dtype=float, copy=True)
            modele.mu_y = float(archive["mu_y"])
            modele.sigma_y = float(archive["sigma_y"])
            # Poids anterieurs au recalage affine : identite, comportement inchange.
            if "echelle_base" in archive:
                modele.echelle_base = float(archive["echelle_base"])
                modele.decalage_base = float(archive["decalage_base"])
        return modele
