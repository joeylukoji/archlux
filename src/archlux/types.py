"""Modèle de données. Aucune dépendance : tout le monde dépend de ce module.

Règles absolues (`ARCHITECTURE.md` §6), vérifiées par les tests de propriété :

- tous les types sont ``frozen=True, slots=True`` — jamais de mutation en place ;
- la position **absolue** d'une ouverture n'est jamais stockée, toujours dérivée ;
- un plan légalisé porte **toujours** son certificat ;
- :class:`PreuveGeometrique` n'a **aucun** champ de probabilité ;
- :class:`BornePerformance` porte **toujours** ``couverture`` et ``n_calibration``.

Unités : mètres, mètres carrés, degrés d'azimut. Origine au coin bas-gauche du contour,
axe ``y`` vers le nord géographique.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from archlux.erreurs import InvariantViole

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "BornePerformance",
    "Certificat",
    "Contexte",
    "Manifeste",
    "ModeleTrace",
    "Mur",
    "Orientation",
    "Ouverture",
    "Piece",
    "Plan",
    "Point",
    "PreuveGeometrique",
    "Referentiel",
    "Structure",
]

Point = tuple[float, float]


# ======================================================================================
# Géométrie
# ======================================================================================


@dataclass(frozen=True, slots=True)
class Piece:
    """Pièce rectangulaire, en mètres, coin bas-gauche en ``(x, y)``.

    Attributes
    ----------
    id : str
        Identifiant stable, unique dans un plan. Sert de clé de tri : l'ordre
        d'itération est toujours explicite, jamais celui d'un ``set``.
    type : str
        Catégorie de programme (``"sejour"``, ``"sdb"``, …). Détermine les seuils
        réglementaires via :class:`Referentiel`.
    x, y, w, h : float
        Position et dimensions, en mètres.
    """

    id: str
    type: str
    x: float
    y: float
    w: float
    h: float

    @property
    def aire(self) -> float:
        """Surface, en mètres carrés."""
        return self.w * self.h

    @property
    def centre(self) -> Point:
        """Centre géométrique, utilisé par ``geom.graphe.deduire_ordre``."""
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)


@dataclass(frozen=True, slots=True)
class Mur:
    """Segment de mur entre deux points, porteur ou non.

    Attributes
    ----------
    porteur : bool
        Un mur porteur est figé : ``geom`` l'écrit dans ``A_eq``, et
        ``certify.preuve`` vérifie qu'il est inchangé en sortie.
    """

    id: str
    a: Point
    b: Point
    porteur: bool = False
    epaisseur: float = 0.10

    @property
    def longueur(self) -> float:
        """Longueur du segment, en mètres."""
        return math.dist(self.a, self.b)


@dataclass(frozen=True, slots=True)
class Ouverture:
    """Baie définie **relativement à son mur**, jamais en coordonnées absolues.

    Stocker une position absolue désynchronise murs et fenêtres dès que le solveur
    déplace une cloison : `ARCHITECTURE.md` §10 en fait un anti-pattern fatal. La
    position absolue se dérive à la demande par :meth:`segment_absolu`.

    Attributes
    ----------
    s : float
        Abscisse du centre le long du mur, dans ``[0, 1]``.
    largeur_rel : float
        Largeur en fraction de la longueur du mur, dans ``]0, 1]``.
    """

    id: str
    mur_id: str
    s: float
    largeur_rel: float
    hauteur_allege: float = 1.00
    hauteur_linteau: float = 2.15

    def segment_absolu(self, mur: Mur) -> tuple[Point, Point]:
        """Dériver les deux extrémités de la baie sur ``mur``.

        Parameters
        ----------
        mur : Mur
            Le mur portant cette ouverture ; son ``id`` doit valoir ``self.mur_id``.

        Returns
        -------
        tuple of Point
            Extrémités de la baie, en coordonnées absolues.

        Raises
        ------
        InvariantViole
            Si ``mur.id`` ne correspond pas à ``self.mur_id``.

        Complexity
        ----------
        O(1).

        Examples
        --------
        >>> from archlux.types import Mur, Ouverture
        >>> mur = Mur(id="m", a=(0.0, 0.0), b=(10.0, 0.0))
        >>> Ouverture(id="f", mur_id="m", s=0.5, largeur_rel=0.2).segment_absolu(mur)
        ((4.0, 0.0), (6.0, 0.0))
        """
        if mur.id != self.mur_id:
            raise InvariantViole(
                (f"ouverture {self.id} portée par {self.mur_id}, dérivée sur {mur.id}",)
            )
        (ax, ay), (bx, by) = mur.a, mur.b
        longueur = mur.longueur
        # Direction unitaire du mur ; un mur dégénéré rendrait une division par zéro,
        # ce que la garde ci-dessous transforme en invariant violé plutôt qu'en NaN.
        if longueur == 0.0:
            raise InvariantViole((f"mur {mur.id} de longueur nulle",))
        ux, uy = (bx - ax) / longueur, (by - ay) / longueur
        cx, cy = ax + (bx - ax) * self.s, ay + (by - ay) * self.s
        demi = self.largeur_rel * longueur / 2.0
        return ((cx - demi * ux, cy - demi * uy), (cx + demi * ux, cy + demi * uy))


@dataclass(frozen=True, slots=True)
class Plan:
    """Un plan d'appartement, proposé ou légalisé.

    Un plan **légalisé** porte toujours son ``certificat`` ; un plan proposé ne l'a
    jamais. Le champ est donc le marqueur de l'état du plan, pas une décoration.

    ``trace`` n'est renseigné que si ``legalize(..., trace=True)`` : c'est la suite
    Frank-Wolfe, **non sérialisée** (elle n'appartient pas au schéma JSON).
    """

    pieces: tuple[Piece, ...]
    murs: tuple[Mur, ...]
    ouvertures: tuple[Ouverture, ...]
    contour: tuple[Point, ...]
    certificat: Certificat | None = None
    # Typé ``object`` à dessein : ``solve.Trace`` vivrait une arête ``types → solve``,
    # interdite. La trace n'est pas sérialisée ; seuls les appelants ``trace=True``
    # la consomment.
    trace: object | None = None

    @property
    def ids_pieces(self) -> tuple[str, ...]:
        """Identifiants de pièces, **triés** — garantit le déterminisme."""
        return tuple(sorted(p.id for p in self.pieces))

    @classmethod
    def from_json(cls, chemin: Path | str) -> Plan:
        """Lire un plan depuis un fichier JSON.

        Façade sur :func:`archlux.io.json_io.charger`. L'import est **local**, à
        l'appel : ``types`` ne dépend de rien à l'import, et aucun cycle n'existe.
        Voir ADR-5 du blueprint et la dérogation nominative de
        ``tests/test_dependances.py``.

        Parameters
        ----------
        chemin : Path or str
            Fichier source.

        Returns
        -------
        Plan
            Plan reconstruit, certificat compris s'il est présent.

        Raises
        ------
        InvariantViole
            Le fichier ne respecte pas le schéma déclaré.
        """
        from archlux.io.json_io import charger

        return charger(chemin)

    def to_json(self, chemin: Path | str) -> None:
        """Écrire ce plan en JSON, clés triées, encodage UTF-8."""
        from archlux.io.json_io import ecrire

        ecrire(self, chemin)


# ======================================================================================
# Contexte
# ======================================================================================


@dataclass(frozen=True, slots=True)
class Orientation:
    """Azimut du plan, en degrés. Variable **circulaire** : voir :mod:`archlux.orient`.

    Traiter 359° et 1° comme éloignés produit des conclusions fausses. Toute statistique
    sur ce champ passe par :mod:`archlux.orient.circulaire`.
    """

    deg: float


@dataclass(frozen=True, slots=True)
class Referentiel:
    """Seuils réglementaires : surfaces et largeurs minimales par type de pièce.

    Un référentiel est **une donnée**, pas du code : changer de réglementation ne doit
    jamais demander de modifier ``geom`` ou ``lmo``.
    """

    aires_min: tuple[tuple[str, float], ...]
    largeur_min: float = 1.80

    def a_min(self, type_piece: str) -> float:
        """Surface minimale exigée pour ``type_piece``, en mètres carrés.

        Parameters
        ----------
        type_piece : str
            Catégorie de programme, telle que portée par :attr:`Piece.type`.

        Returns
        -------
        float
            Le seuil, ou ``0.0`` si le type n'est pas réglementé. Un type inconnu ne
            lève pas : « pas de seuil » et « seuil nul » ont le même effet sur le
            polytope, et distinguer les deux ferait porter la nuance à tout appelant.

        Complexity
        ----------
        O(k), k = nombre de types réglementés — une poignée en pratique.
        """
        for type_connu, seuil in self.aires_min:
            if type_connu == type_piece:
                return seuil
        return 0.0


@dataclass(frozen=True, slots=True)
class Structure:
    """Structure porteuse : ce que le solveur n'a pas le droit de déplacer."""

    murs_porteurs: tuple[Mur, ...]
    poteaux: tuple[Point, ...] = ()


@dataclass(frozen=True, slots=True)
class Contexte:
    """Tout ce qui n'est pas le plan : structure, orientation, contour, référentiel.

    Séparer ``Plan`` et ``Contexte`` est ce qui permet à ``legalize`` d'avoir deux
    arguments et non douze, et rend le contexte réutilisable sur un lot de plans.
    """

    structure: Structure
    orientation: Orientation
    contour: tuple[Point, ...]
    referentiel: Referentiel
    programme: tuple[str, ...] = ()


# ======================================================================================
# Certificat — les deux garanties, séparées par construction
# ======================================================================================


@dataclass(frozen=True, slots=True)
class PreuveGeometrique:
    """Garantie **exacte**, vérifiée indépendamment du solveur.

    Ce type ne contient **aucun champ de probabilité** et ne doit jamais en contenir.
    C'est la thèse du projet inscrite dans le système de types : une preuve et une
    prédiction ne sont pas de même nature, et rien ne doit permettre de les mélanger.
    """

    valide: bool
    chevauchement: bool
    jours: bool
    surfaces_ok: bool
    structure_preservee: bool
    deplacement_max: float
    violations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BornePerformance:
    """Garantie **probabiliste** : intervalle à couverture ``≥ 1 − α``.

    ``couverture`` et ``n_calibration`` sont obligatoires : une borne conforme sans son
    niveau de couverture ni sa taille de calibration est invérifiable, donc sans valeur.
    """

    indicateur: Literal["sDA", "ASE", "UDI", "vue"]
    valeur: float
    borne_inf: float
    borne_sup: float
    couverture: float
    n_calibration: int

    def __post_init__(self) -> None:
        """Refuser une borne sans jeu de calibration, ou une couverture hors ]0, 1]."""
        if self.n_calibration < 1:
            raise InvariantViole(("n_calibration doit être ≥ 1",))
        if not 0.0 < self.couverture <= 1.0:
            raise InvariantViole((f"couverture hors ]0, 1] : {self.couverture}",))


@dataclass(frozen=True, slots=True)
class ModeleTrace:
    """Empreinte du modèle et taille de calibration — champs du manifeste de banc.

    ``poids`` est une empreinte (SHA), jamais le tenseur lui-même.
    """

    poids: str
    calibration_n: int
    alpha: float

    def __post_init__(self) -> None:
        """Valider empreinte, taille de calibration et niveau α."""
        if not self.poids:
            raise InvariantViole(("empreinte de poids obligatoire",))
        if self.calibration_n < 1:
            raise InvariantViole(("calibration_n doit être ≥ 1",))
        if not 0.0 < self.alpha < 1.0:
            raise InvariantViole((f"alpha hors ]0, 1[ : {self.alpha}",))

    def __getitem__(self, cle: str) -> str | int | float:
        """Accès dictionnaire pour les assertions de manifeste (`MILESTONE-6`)."""
        try:
            return getattr(self, cle)  # type: ignore[no-any-return]
        except AttributeError as exc:
            raise KeyError(cle) from exc


@dataclass(frozen=True, slots=True)
class Manifeste:
    """Trace de reproductibilité émise à chaque exécution, sans exception.

    Les champs sont des tuples de paires et non des ``dict`` : le manifeste est gelé et
    doit se sérialiser dans un ordre stable, sinon son empreinte n'est pas reproductible.
    """

    version: str
    horodatage: str
    graine: int
    empreinte_donnees: str | None = None
    decoupage: str | None = None
    environnement: tuple[tuple[str, str], ...] = ()
    parametres: tuple[tuple[str, str], ...] = ()
    modele: ModeleTrace | None = None


@dataclass(frozen=True, slots=True)
class Certificat:
    """Preuve exacte + borne probabiliste optionnelle + diagnostic dual.

    ``performance`` vaut ``None`` en légalisation classique : il n'y a alors rien de
    probabiliste à affirmer, et le certificat doit le dire plutôt que de le suggérer.

    Attributes
    ----------
    duaux : tuple of (str, float)
        Prix duaux **déjà traduits** via ``Polytope.origines`` : ``("mur porteur axe 3",
        4.1)``. Jamais un indice de ligne nu.
    """

    geometrie: PreuveGeometrique
    performance: BornePerformance | None = None
    duaux: tuple[tuple[str, float], ...] = ()
    manifeste: Manifeste | None = None

    def rapport(self) -> str:
        """Rendre le certificat en texte, sections ``[EXACT]`` et ``[PREDICTION]``.

        Façade sur :func:`archlux.certify.rapport.rendre`, par import local — même
        motif que :meth:`Plan.from_json`, même dérogation nominative (ADR-5). Le rendu
        lui-même reste dans ``certify`` : ce type ne sait pas mettre en forme, il sait
        seulement à qui le demander.

        Returns
        -------
        str
            Rapport lisible. Les deux natures de garantie sont toujours séparées
            visuellement et jamais agrégées en un score unique.
        """
        from archlux.certify.rapport import rendre

        return rendre(self)
