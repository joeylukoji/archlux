"""Protocole ``Substitut`` : la **seule** interface entre le noyau pur et l'appris.

Trois méthodes, pas une de plus. C'est cette étroitesse qui permet trois implémentations
interchangeables — analytique (formules fermées), apprise (transformeur), simulateur
exact — sans que ``solve`` ne sache laquelle il manipule.

`solve` dépend de **ce fichier**, jamais de :mod:`archlux.light.appris`. Le test de
dépendance (`tests/test_dependances.py`) fait échouer la CI si cette règle est franchie.

Entrée **vectorielle uniquement**. Un substitut prenant une image en entrée a un gradient
nul presque partout : l'optimiseur devient aveugle et le projet est impossible
(`ARCHITECTURE.md` §10, premier anti-pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np

    from archlux.types import Mur, Orientation, Ouverture

__all__ = ["Baies", "Substitut", "SubstitutParPiece", "WrapsSurrogate", "point_prediction"]


@dataclass(frozen=True, slots=True)
class Baies:
    """Fenestration d'un plan, **invariante** pendant l'optimisation.

    Le vecteur de décision ne porte que ``(x, y, w, h)`` par pièce : il ne dit
    **rien** des ouvertures. Or ce sont elles qui déterminent l'éclairement.
    Mesuré sur 369 appartements suisses, cible = irradiance simulée par lancer de
    rayons, découpage par site : le substitut analytique obtient ``R² = −0,000``
    et le perceptron ``R² = −0,667``, tous deux au niveau — ou en dessous — de la
    simple moyenne. Aucun modèle ne peut faire mieux à partir de rectangles sans
    fenêtres ; ce n'est pas un défaut de capacité, c'est un défaut d'entrée.

    Les baies sont décrites **relativement à leur mur** (`ARCHITECTURE.md` §10) et
    ne bougent pas pendant Frank-Wolfe : seules les cloisons se déplacent, et les
    ouvertures suivent sans synchronisation. Cet objet se construit donc une fois,
    au départ, et se transmet inchangé à chaque itération.

    Attributes
    ----------
    murs : tuple of Mur
        Murs porteurs des ouvertures. Nécessaires pour dériver une position
        absolue à la demande, jamais pour la stocker.
    ouvertures : tuple of Ouverture
        Baies, en coordonnées relatives ``(mur_id, s, largeur_rel)``.
    """

    murs: tuple[Mur, ...] = ()
    ouvertures: tuple[Ouverture, ...] = ()

    @property
    def vide(self) -> bool:
        """Dire si aucune fenestration n'est décrite.

        Un substitut qui reçoit des baies vides doit se comporter **exactement**
        comme s'il n'en avait pas reçu : c'est ce qui rend l'extension du
        protocole rétrocompatible.
        """
        return not self.ouvertures


@runtime_checkable
class SubstitutParPiece(Protocol):
    """Substitut qui expose ses valeurs **par pièce**, et pas seulement leur somme.

    Pourquoi ce protocole existe
    ----------------------------
    :class:`Substitut` rend **un scalaire par plan**. L'éclairement est une
    grandeur **par pièce**, et la mesure est sans appel : sur 367 466 pièces de
    Swiss Dwellings, **92 % de la variance est intra-appartement**. L'identité
    du bâtiment — qui porte masque urbain, climat et position solaire —
    n'explique que 2,6 %.

    Agréger en moyenne de logement revient donc à prédire une quantité dont la
    variance ne pèse que 7,7 % du phénomène. C'est ce qui explique les
    ``R² ≈ 0`` mesurés, davantage que la pauvreté des entrées.

    Conséquence : **aucun indicateur de type sDA n'est représentable** par un
    scalaire de plan. Le sDA se définit par pièce — part du sol au-dessus de
    300 lux — jamais par logement.

    Ce protocole est **facultatif** et **additif**. ``solve`` continue de
    n'utiliser que :class:`Substitut` : la scalarisation reste explicite et à
    la charge de l'appelant, ce qui évite qu'une moyenne implicite se glisse
    dans l'objectif d'optimisation.
    """

    def evaluer_pieces(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        """Rendre une valeur par pièce, dans l'ordre de ``Polytope.index``.

        Returns
        -------
        numpy.ndarray
            Dimension ``len(x) // 4`` — une valeur par pièce.

        Guarantees
        ----------
        - Cohérence : la scalarisation retenue par l'implémentation doit
          redonner :meth:`Substitut.evaluer`. Pour les substituts analytiques
          du dépôt, c'est la **somme** — vérifié par test.
        """
        ...


@runtime_checkable
class Substitut(Protocol):
    """Modèle différentiable d'un indicateur d'éclairement.

    Toute implémentation respecte trois obligations :

    1. l'entrée est le vecteur de décision du polytope, jamais un raster — et,
       depuis l'extension du protocole, les :class:`Baies` qui l'accompagnent ;
    2. :meth:`gradient` est cohérent avec :meth:`evaluer` — vérifié par
       :func:`archlux.light.validation.valider_gradient` ;
    3. :meth:`incertitude` ne rend jamais un scalaire nu sans son échelle.
    """

    @property
    def indicateur(self) -> str:
        """Nom de l'indicateur modélisé (``"sDA"``, ``"ASE"``, …)."""
        ...

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Estimer l'indicateur pour le plan encodé par ``x``.

        Parameters
        ----------
        x : numpy.ndarray
            Vecteur de décision, ordonné par ``Polytope.index``.
        orientation : Orientation
            Azimut, traité comme variable circulaire.
        baies : Baies or None, optional
            Fenestration, constante pendant l'optimisation. ``None`` — le défaut —
            signifie « information absente » : l'implémentation doit alors se
            rabattre sur son hypothèse par défaut, comme avant l'extension du
            protocole. Une implémentation a le droit de l'ignorer.

        Returns
        -------
        float
            Estimation ponctuelle. **Sans garantie** en soi : la garantie vient de
            :mod:`archlux.uq`, qui l'assortit d'un intervalle conforme.

        Guarantees
        ----------
        - Performance : **probabiliste uniquement**, et seulement une fois la valeur
          passée par la calibration conforme. Cette méthode seule ne garantit rien.
        """
        ...

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        """Rendre ∂indicateur/∂x, dans la base du polytope.

        C'est **tout** ce que l'apprentissage fournit au système : une direction. Le
        générateur décide l'ordre, le solveur décide les dimensions.

        Returns
        -------
        numpy.ndarray
            Même dimension que ``x``.
        """
        ...

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Écart-type prédictif, en unité de l'indicateur.

        Sert de score de non-conformité à :mod:`archlux.uq.conforme` et de critère
        d'échantillonnage à l'apprentissage actif du jalon 6.
        """
        ...


@runtime_checkable
class WrapsSurrogate(Protocol):
    """An objective built on a surrogate, such as the pessimistic ``Daylight``.

    Its :meth:`Substitut.evaluer` may return ``mu - q sigma`` rather than a prediction;
    ``substitut`` gives access to the prediction itself (PLAN.md batch 1.6).
    """

    @property
    def substitut(self) -> Substitut:
        """The wrapped surrogate, whose ``evaluer`` is a point prediction."""
        ...


def point_prediction(
    objective: Substitut, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
) -> tuple[float, float]:
    """Point prediction ``mu`` and uncertainty ``sigma`` behind an objective.

    ``mu`` is in the sign of the indicator (see below).

    A conformal interval is centred on the prediction, never on a pessimistic objective:
    centring it on ``mu - q sigma`` would subtract the margin twice. Every wrapping layer
    is removed, so that ``Daylight(Daylight(s))`` does not keep one margin.

    Surrogates return ASE **negated**, so that Frank-Wolfe, which maximizes, reduces
    glare (:class:`archlux.light.analytique.SubstitutAnalytique`). The prediction is
    given back as a positive ASE, the quantity the calibration and the report read.
    """
    surrogate: Substitut = objective
    while isinstance(surrogate, WrapsSurrogate):
        surrogate = surrogate.substitut
    mu = float(surrogate.evaluer(x, orientation, baies=baies))
    sigma = float(surrogate.incertitude(x, orientation, baies=baies))
    if surrogate.indicateur == "ASE":
        mu = -mu
    return mu, sigma
