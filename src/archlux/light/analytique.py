"""Substitut en formes fermées — **sans aucun apprentissage**.

Son intérêt n'est pas la précision : c'est de faire tourner la chaîne complète au
troisième mois plutôt qu'au dix-huitième. Si l'architecture est fausse, elle est fausse
ici, avant toute dépense de simulation ou d'entraînement.

Implémente :class:`archlux.light.protocole.Substitut`. Entrée vectorielle uniquement.

Le facteur d'orientation passe par :func:`archlux.orient.circulaire.encoder` : jamais
le degré brut. Formules : ``docs/formules/substitut-analytique.md``.

Ce module n'importe ni ``geom`` ni ``lmo`` ni ``solve`` : uniquement un vecteur et un
azimut (`ARCHITECTURE.md` §5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Literal

import numpy as np

from archlux.light.protocole import Baies
from archlux.orient.circulaire import encoder
from archlux.types import Orientation

__all__ = ["FACTEURS_SECTEUR", "SubstitutAnalytique", "facteur_secteur"]

_EPS = 1e-12
_N_CHAMPS = 4
"""Même contrat que ``geom.polytope.CHAMPS`` : ``(x, y, w, h)`` par pièce. Dupliqué
ici pour que ``light`` n'importe pas ``geom``.
"""

FACTEURS_SECTEUR: tuple[float, ...] = (
    0.45,
    0.55,
    0.70,
    0.90,
    1.00,
    0.90,
    0.70,
    0.55,
)
"""Huit secteurs N, NE, E, SE, S, SW, W, NW. Le sud (180 degres) est le plus favorable.

**Table d'atelier, pas une source citee.** Ces huit poids ne viennent d'aucune norme :
CIBSE LG10 donne une profondeur limite independante de l'azimut, et le split-flux BRE
travaille sous ciel couvert CIE, donc lui aussi sans azimut. Ils encodent la preference
sud d'un climat de l'hemisphere nord pour que l'argmax de l'optimiseur depende de
l'orientation. Un article doit les presenter comme un a priori de modelisation, calibre
ou remplace par une simulation annuelle, jamais comme la regle citee.
"""


def facteur_secteur(orientation: Orientation) -> float:
    """Poids d'exposition du secteur de 45 degres contenant ``orientation``.

    Passe par :func:`archlux.orient.circulaire.encoder`, jamais par le degre brut :
    l'azimut est reconstruit depuis ``(cos, sin)``, donc continu en 0 / 360.

    Parameters
    ----------
    orientation : Orientation
        Azimut du batiment.

    Returns
    -------
    float
        Un element de :data:`FACTEURS_SECTEUR`, dans ``[0.45, 1.00]``.
    """
    features = encoder(orientation, harmoniques=1)
    azimut = float(np.degrees(np.arctan2(features[1], features[0]))) % 360.0
    secteur = int((azimut + 22.5) // 45.0) % 8
    return FACTEURS_SECTEUR[secteur]


@dataclass(frozen=True, slots=True)
class SubstitutAnalytique:
    """Modèle de facteur de lumière du jour par règle de profondeur limite.

    La profondeur au-delà de laquelle une pièce cesse d'être éclairée naturellement
    dépend fortement de l'exposition : le modèle module cette profondeur par
    l'orientation, encodée circulairement, et favorise les pièces situées au sud
    géographique (sinon toutes les orientations donneraient le même argmax).

    Attributes
    ----------
    indicateur_vise : {"sDA", "ASE", "UDI", "vue"}
        Grandeur rendue par :meth:`evaluer`. ASE est renvoyé *négatif* pour que
        Frank-Wolfe, qui maximise, réduise l'éblouissement.
    sigma_nominal : float
        Écart-type constant. Ce substitut ne modélise pas son erreur.
    """

    indicateur_vise: Literal["sDA", "ASE", "UDI", "vue"] = "sDA"
    sigma_nominal: float = 0.08

    FACTEUR_PROFONDEUR: ClassVar[float] = 2.5
    """Règle usuelle : profondeur utile ≈ 2,5 fois la hauteur de linteau (CIBSE LG10)."""

    HAUTEUR_LINTEAU: ClassVar[float] = 2.15
    """Linteau typique, en mètres. Marge d'incertitude de la règle : ~30 %."""

    KAPPA_SUD: ClassVar[float] = 0.15
    """Poids, en 1/m, du placement vers le sud géographique."""

    FACTEURS_SECTEUR: ClassVar[tuple[float, ...]] = FACTEURS_SECTEUR
    """Alias de classe vers :data:`FACTEURS_SECTEUR` (contrat public conservé)."""

    @property
    def indicateur(self) -> str:
        """Nom de l'indicateur modélisé."""
        return self.indicateur_vise

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Estimer l'indicateur en formes fermées.

        ``baies`` est **ignoré** : ce substitut ne modélise pas la fenestration,
        il suppose un bandeau vitré constant. C'est précisément ce qui lui vaut
        ``R² = −0,000`` contre une irradiance simulée.

        Guarantees
        ----------
        - Performance : **aucune garantie en soi**. La valeur devient bornée seulement
          après passage par :mod:`archlux.uq.conforme`.
        """
        del baies
        return float(self._score_et_gradient(x, orientation, avec_gradient=False)[0])

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        """Gradient analytique, dérivé à la main puis validé par différences finies.

        **Exact** partout sauf en deux endroits, tous deux de mesure nulle :
        au coude ``profondeur == profondeur_utile`` (dérivée à gauche retenue) et sous
        les seuils ``w < 1e-12`` / ``h < 1e-12``, où ``evaluer`` écrête mais où la
        dérivée écrite ignore l'écrêtage. Hors de ces points, la vérification
        symbolique donne l'égalité stricte avec ``∂ evaluer / ∂ x``.
        """
        del baies
        return self._score_et_gradient(x, orientation, avec_gradient=True)[1]

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Écart-type nominal constant : ce substitut ne modélise pas son erreur."""
        del x, orientation, baies
        return float(self.sigma_nominal)

    def evaluer_pieces(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        """Contribution de chaque pièce, avant sommation.

        ``evaluer`` en est la somme, au signe d'ASE près. Voir
        :class:`~archlux.light.protocole.SubstitutParPiece` : c'est à cette
        granularité que vit 92 % de la variance de l'éclairement réel.
        """
        del baies
        parts = self._parts(x, orientation)
        return -parts if self.indicateur_vise == "ASE" else parts

    def _parts(self, x: np.ndarray, orientation: Orientation) -> np.ndarray:
        """Score positif de chaque pièce, sans le signe de l'indicateur."""
        vecteur = np.asarray(x, dtype=float).ravel()
        n_pieces = vecteur.size // _N_CHAMPS
        features = encoder(orientation, harmoniques=1)
        cos_t, sin_t = float(features[0]), float(features[1])
        cos2, sin2 = cos_t * cos_t, sin_t * sin_t
        profondeur_utile = (
            self.FACTEUR_PROFONDEUR * self.HAUTEUR_LINTEAU * self._facteur_orientation(orientation)
        )
        parts = np.zeros(n_pieces, dtype=float)
        for i in range(n_pieces):
            base = i * _N_CHAMPS
            pos_x, pos_y = float(vecteur[base]), float(vecteur[base + 1])
            largeur = max(float(vecteur[base + 2]), _EPS)
            hauteur = max(float(vecteur[base + 3]), _EPS)
            facade_sud = largeur * cos2 + hauteur * sin2
            profondeur = largeur * sin2 + hauteur * cos2
            penetration = min(profondeur, profondeur_utile)
            sudness = -pos_x * sin_t - pos_y * cos_t
            parts[i] = facade_sud * penetration * math.exp(self.KAPPA_SUD * sudness)
        return parts

    def _facteur_orientation(self, orientation: Orientation) -> float:
        """Table à 8 secteurs. Délègue à :func:`facteur_secteur`, sans état."""
        return facteur_secteur(orientation)

    def _score_et_gradient(
        self, x: np.ndarray, orientation: Orientation, *, avec_gradient: bool
    ) -> tuple[float, np.ndarray]:
        """Score scalaire et, si demandé, ∇x du même scalaire."""
        vecteur = np.asarray(x, dtype=float).ravel()
        n_pieces = vecteur.size // _N_CHAMPS
        gradient = np.zeros_like(vecteur, dtype=float)

        features = encoder(orientation, harmoniques=1)
        cos_t = float(features[0])
        sin_t = float(features[1])
        cos2 = cos_t * cos_t
        sin2 = sin_t * sin_t
        profondeur_utile = (
            self.FACTEUR_PROFONDEUR * self.HAUTEUR_LINTEAU * self._facteur_orientation(orientation)
        )

        total = 0.0
        for i in range(n_pieces):
            base = i * _N_CHAMPS
            pos_x, pos_y = float(vecteur[base]), float(vecteur[base + 1])
            largeur, hauteur = float(vecteur[base + 2]), float(vecteur[base + 3])
            largeur = max(largeur, _EPS)
            hauteur = max(hauteur, _EPS)

            facade_sud = largeur * cos2 + hauteur * sin2
            profondeur = largeur * sin2 + hauteur * cos2
            # min(profondeur, profondeur_utile) : la penetration est continue mais
            # **non differentiable** en profondeur == profondeur_utile. La convention
            # retenue est la derivee a GAUCHE (d_pen_d_p = 1) ; a droite elle vaut 0.
            # Au coude exact, aucune difference finie centree ne peut retrouver la
            # valeur declaree : valider_gradient y verifie des signes, pas une egalite.
            if profondeur <= profondeur_utile:
                penetration = profondeur
                d_pen_d_p = 1.0
            else:
                penetration = profondeur_utile
                d_pen_d_p = 0.0
            utile = facade_sud * penetration

            sudness = -pos_x * sin_t - pos_y * cos_t
            poids_sud = math.exp(self.KAPPA_SUD * sudness)
            score = utile * poids_sud
            total += score

            if not avec_gradient:
                continue

            d_u_d_l = penetration
            d_u_d_p = facade_sud * d_pen_d_p
            du_dw = d_u_d_l * cos2 + d_u_d_p * sin2
            du_dh = d_u_d_l * sin2 + d_u_d_p * cos2

            kappa = self.KAPPA_SUD
            gradient[base] = score * kappa * (-sin_t)
            gradient[base + 1] = score * kappa * (-cos_t)
            gradient[base + 2] = du_dw * poids_sud
            gradient[base + 3] = du_dh * poids_sud

        if self.indicateur_vise == "ASE":
            return -total, -gradient
        return total, gradient
