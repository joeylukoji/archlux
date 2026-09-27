"""Oracle d'éclairement — split-flux BRE, même protocole ``Surrogate``.

La CI utilise cette forme fermée, **plus riche** que l'analytique (CIBSE profondeur),
pour que le réseau puisse la battre et que le point de contrôle du gradient soit
exécutable. Un moteur de lancer de rayons (Radiance) est hors chemin critique.

Le DF moyen d'une pièce suit Littlefair / BRE : baie = WWR × façade éclairée
(déjà dans le vecteur ``(w, h)``), sans élargir le protocole ``Surrogate``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.light.analytique import AnalyticSurrogate, sector_factor
from archlux.light.jetons import FIELDS_PER_ROOM
from archlux.light.protocole import Glazing
from archlux.orient.circulaire import encode_orientation
from archlux.types import Indicator, Orientation

__all__ = ["SplitFluxOracle", "daylight_factor"]

_EPS = 1e-12
_TRANSMITTANCE = 0.70
_REFLECTANCE = 0.50
_THETA_CIEL_DEG = 65.0
_HAUTEUR_PLAFOND = 2.70
_HAUTEUR_VITRAGE = 1.15
_WWR_DEFAUT = 0.30
_DENOM_REFLET = 1.0 - _REFLECTANCE * _REFLECTANCE


def _facade_sud(w: float, h: float, orientation: Orientation) -> float:
    """Longueur de façade au sud géographique, même convention que l'analytique."""
    features = encode_orientation(orientation, harmoniques=1)
    cos2 = float(features[0]) ** 2
    sin2 = float(features[1]) ** 2
    return w * cos2 + h * sin2


def _derivees_facade(orientation: Orientation) -> tuple[float, float]:
    """∂L/∂w et ∂L/∂h pour la façade sud."""
    features = encode_orientation(orientation, harmoniques=1)
    cos2 = float(features[0]) ** 2
    sin2 = float(features[1]) ** 2
    return cos2, sin2


def daylight_factor(
    w: float,
    h: float,
    orientation: Orientation,
    *,
    wwr: float = _WWR_DEFAUT,
) -> float:
    """Facteur de lumière du jour moyen (fraction, pas un sDA LM-83).

    Formule split-flux BRE / Littlefair, ciel couvert, baie sur la façade sud :

    ``DF = T A_w θ / (A_surf (1 − R²))`` en pourcent, rendu ici en fraction.

    Parameters
    ----------
    w, h : float
        Côtés du rectangle, en mètres, même contrat que le polytope.
    orientation : Orientation
        Azimut du bâtiment. Module l'angle de ciel via les 8 secteurs.
    wwr : float, optional
        Facteur de bandeau vitré, dans ``]0, 1]``. Défaut 0,30 (imputation jalon 4).

    Returns
    -------
    float
        Éclairement relatif moyen, dans ``[0, 1]`` (2 % → ``0.02``).

    Notes
    -----
    Deux écarts assumés à la source citée, à déclarer dans toute publication :

    1. **θ dépend de l'azimut ici.** Dans BRE / Littlefair, θ est l'angle de ciel
       visible, une grandeur purement géométrique (obstructions), et le ciel CIE
       couvert est isotrope : le DF moyen y est **indépendant de l'orientation**.
       Le facteur ``facteur_secteur`` est un a priori de modélisation ajouté par
       archlux pour que l'optimiseur distingue les azimuts ; il fait sortir la formule
       du cadre où elle est validée. ``θ = 65°`` (au lieu de 90° sans obstruction) est
       de même une hypothèse d'obstruction urbaine non mesurée.
    2. **``wwr`` n'est pas un window-to-wall ratio.** L'aire de baie vaut ici
       ``wwr × 1,15 m × longueur_de_façade`` : la hauteur du bandeau est déjà dans la
       formule, donc ``wwr`` la module une seconde fois. Le WWR effectif d'un
       ``wwr = 0,30`` sur un étage de 2,70 m est ``0,30 × 1,15 / 2,70 ≈ 0,13``.
       Le paramètre est un coefficient de bandeau, et devrait être renommé.
    """
    return _split_flux(w, h, orientation, wwr, avec_gradient=False)[0]


def _split_flux(
    w: float,
    h: float,
    orientation: Orientation,
    wwr: float,
    *,
    avec_gradient: bool,
) -> tuple[float, float, float]:
    """DF fractionnaire et, si demandé, ∂DF/∂w et ∂DF/∂h."""
    if wwr <= 0.0 or wwr > 1.0:
        raise InvariantViolation((f"wwr hors ]0, 1] : {wwr}",))
    w = max(float(w), _EPS)
    h = max(float(h), _EPS)
    theta = _THETA_CIEL_DEG * sector_factor(orientation)
    facade = max(_facade_sud(w, h, orientation), _EPS)
    aire_baie = wwr * _HAUTEUR_VITRAGE * facade
    aire_surf = 2.0 * w * h + 2.0 * (w + h) * _HAUTEUR_PLAFOND
    numerateur = _TRANSMITTANCE * aire_baie * theta
    denominateur = max(aire_surf * _DENOM_REFLET, _EPS)
    df_pct = numerateur / denominateur
    df = df_pct / 100.0
    if not avec_gradient:
        return df, 0.0, 0.0
    dL_dw, dL_dh = _derivees_facade(orientation)
    dAw_dw = wwr * _HAUTEUR_VITRAGE * dL_dw
    dAw_dh = wwr * _HAUTEUR_VITRAGE * dL_dh
    dAs_dw = 2.0 * h + 2.0 * _HAUTEUR_PLAFOND
    dAs_dh = 2.0 * w + 2.0 * _HAUTEUR_PLAFOND
    dnum_dw = _TRANSMITTANCE * theta * dAw_dw
    dnum_dh = _TRANSMITTANCE * theta * dAw_dh
    dden_dw = _DENOM_REFLET * dAs_dw
    dden_dh = _DENOM_REFLET * dAs_dh
    d_pct_dw = (dnum_dw * denominateur - numerateur * dden_dw) / (denominateur * denominateur)
    d_pct_dh = (dnum_dh * denominateur - numerateur * dden_dh) / (denominateur * denominateur)
    return df, d_pct_dw / 100.0, d_pct_dh / 100.0


@dataclass(frozen=True, slots=True)
class SplitFluxOracle:
    """Frozen deterministic oracle: CIBSE analytic surrogate plus BRE split-flux daylight.

    A closed form, **not** a simulation and not ground truth: it lets the CI exercise
    the whole chain against a fixed reference. Formerly ``SimulateurExact``.

    Oracle déterministe : analytique CIBSE + split-flux BRE sur les façades.

    Le terme d'aire × sin 2θ (jouet) est remplacé par un DF cité. Pour ``ASE``,
    l'analytique rend déjà l'opposé ; le split-flux est nié une seule fois.
    """

    indicateur_vise: Indicator = "sDA"
    sigma_nominal: float = 0.04
    wwr: float = _WWR_DEFAUT
    ECHELLE_DF: ClassVar[float] = 100.0
    """Poids m²·% : ``100 * DF * aire`` pour rester à l'échelle de l'analytique.

    Ce ``100`` **annule exactement** la division par 100 de ``facteur_lumiere_jour``,
    qui convertit le DF de pourcent en fraction. Le terme ajoute au score vaut donc
    ``DF[%] * aire[m2]`` : une unite composite (m2 pour cent), pas un indicateur
    normalise. L'aller-retour fraction / pourcent n'existe que pour garder l'API
    publique de ``facteur_lumiere_jour`` en fraction. La constante n'est donc pas un
    reglage libre : la changer desaccorderait les deux echelles.
    """

    @property
    def indicator(self) -> Indicator:
        """Nom de l'étiquette visée. Le scalaire rendu n'est pas un sDA LM-83."""
        return self.indicateur_vise

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Score déterministe. Deux appels identiques rendent le même flottant.

        ``baies`` est ignoré : le WWR est une constante du modèle, pas une
        lecture de la fenestration réelle.
        """
        del glazing
        return float(self._score_et_gradient(x, orientation, avec_gradient=False)[0])

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Gradient analytique du même score (CIBSE + split-flux)."""
        del glazing
        return self._score_et_gradient(x, orientation, avec_gradient=True)[1]

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Écart-type nominal constant : pas d'erreur apprise."""
        del x, orientation, glazing
        return float(self.sigma_nominal)

    def evaluate_rooms(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Contribution de chaque piece : analytique + split-flux, avant sommation.

        ``evaluate`` en est la somme. Voir
        :class:`~archlux.light.protocole.SubstitutParPiece`.
        """
        del glazing
        base = AnalyticSurrogate(indicateur_vise=self.indicateur_vise)
        parts = np.asarray(base.evaluate_rooms(x, orientation), dtype=float).copy()
        vecteur = np.asarray(x, dtype=float).ravel()
        signe = -1.0 if self.indicateur_vise == "ASE" else 1.0
        for i in range(vecteur.size // FIELDS_PER_ROOM):
            largeur = float(vecteur[i * FIELDS_PER_ROOM + 2])
            hauteur = float(vecteur[i * FIELDS_PER_ROOM + 3])
            df, _, _ = _split_flux(largeur, hauteur, orientation, self.wwr, avec_gradient=False)
            aire = max(largeur, _EPS) * max(hauteur, _EPS)
            parts[i] += signe * self.ECHELLE_DF * df * aire
        return parts

    def _score_et_gradient(
        self, x: np.ndarray, orientation: Orientation, *, avec_gradient: bool
    ) -> tuple[float, np.ndarray]:
        base = AnalyticSurrogate(indicateur_vise=self.indicateur_vise)
        valeur = float(base.evaluate(x, orientation))
        gradient = (
            np.asarray(base.gradient(x, orientation), dtype=float).copy()
            if avec_gradient
            else np.zeros_like(np.asarray(x, dtype=float).ravel())
        )
        vecteur = np.asarray(x, dtype=float).ravel()
        n_pieces = vecteur.size // FIELDS_PER_ROOM
        signe_extra = -1.0 if self.indicateur_vise == "ASE" else 1.0
        extra = 0.0
        for i in range(n_pieces):
            largeur = float(vecteur[i * FIELDS_PER_ROOM + 2])
            hauteur = float(vecteur[i * FIELDS_PER_ROOM + 3])
            df, d_df_dw, d_df_dh = _split_flux(
                largeur, hauteur, orientation, self.wwr, avec_gradient=avec_gradient
            )
            aire = max(largeur, _EPS) * max(hauteur, _EPS)
            extra += df * aire
            if avec_gradient:
                d_aire_dw = max(hauteur, _EPS)
                d_aire_dh = max(largeur, _EPS)
                gradient[i * FIELDS_PER_ROOM + 2] += (
                    signe_extra * self.ECHELLE_DF * (d_df_dw * aire + df * d_aire_dw)
                )
                gradient[i * FIELDS_PER_ROOM + 3] += (
                    signe_extra * self.ECHELLE_DF * (d_df_dh * aire + df * d_aire_dh)
                )
        valeur += signe_extra * self.ECHELLE_DF * extra
        return valeur, gradient


__getattr__ = lazy_aliases(
    __name__,
    {
        "facteur_lumiere_jour": Alias(daylight_factor, "archlux.light.simulateur.daylight_factor"),
        "SimulateurExact": Alias(
            SplitFluxOracle,
            "SplitFluxOracle",
            note="a frozen split-flux oracle, neither a simulation nor ground truth",
        ),
    },
)
