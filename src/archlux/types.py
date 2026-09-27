"""Modèle de données. Aucune dépendance : tout le monde dépend de ce module.

Règles absolues (`ARCHITECTURE.md` §6), vérifiées par les tests de propriété :

- tous les types sont ``frozen=True, slots=True`` — jamais de mutation en place ;
- la position **absolue** d'une ouverture n'est jamais stockée, toujours dérivée ;
- un plan légalisé porte **toujours** son certificat ;
- :class:`GeometricProof` n'a **aucun** champ de probabilité ;
- :class:`PerformanceBound` porte **toujours** ``couverture`` et ``n_calibration``.

Unités : mètres, mètres carrés, degrés d'azimut. Origine au coin bas-gauche du contour,
axe ``y`` vers le nord géographique.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvalidInput, InvariantViolation

if TYPE_CHECKING:
    from archlux.export import RapportExport

__all__ = [
    "Certificate",
    "Context",
    "GeometricProof",
    "Indicateur",
    "Manifest",
    "ModelTrace",
    "Opening",
    "Orientation",
    "PerformanceBound",
    "Plan",
    "Point",
    "Regulation",
    "Room",
    "Structure",
    "Wall",
]

Point = tuple[float, float]

Indicateur = Literal["sDA", "ASE", "UDI", "vue"]
"""Daylight indicator modelled by a surrogate and bounded by a certificate. Written once:
``PerformanceBound``, the ``Substitut`` protocol, the surrogates and the calibration all
share it."""


# ======================================================================================
# Géométrie
# ======================================================================================


@dataclass(frozen=True, slots=True, kw_only=True)
class Room:
    """Pièce rectangulaire, en mètres, coin bas-gauche en ``(x, y)``.

    Attributes
    ----------
    id : str
        Identifiant stable, unique dans un plan. Sert de clé de tri : l'ordre
        d'itération est toujours explicite, jamais celui d'un ``set``.
    type : str
        Catégorie de programme (``"sejour"``, ``"sdb"``, …). Détermine les seuils
        réglementaires via :class:`Regulation`.
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


@dataclass(frozen=True, slots=True, kw_only=True)
class Wall:
    """Segment de mur entre deux points, porteur ou non.

    Attributes
    ----------
    porteur : bool
        A load-bearing wall is fixed: ``geom`` keeps every room on its side (one
        inequality per room, see :class:`archlux.geom.graphe.WallSide`), and
        ``certify.proof`` checks that no room crosses it.
    """

    id: str
    a: Point
    b: Point
    load_bearing: bool = False
    thickness: float = 0.10

    @property
    def longueur(self) -> float:
        """Longueur du segment, en mètres."""
        return math.dist(self.a, self.b)


@dataclass(frozen=True, slots=True, kw_only=True)
class Opening:
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
    wall_id: str
    s: float
    relative_width: float
    sill_height: float = 1.00
    head_height: float = 2.15

    def __post_init__(self) -> None:
        """Refuse ``s`` outside ``[0, 1]`` and ``relative_width`` outside ``]0, 1]``."""
        if not 0.0 <= self.s <= 1.0:
            raise InvalidInput(f"ouvertures[{self.id}].s", f"must be in [0, 1], got {self.s}")
        if not 0.0 < self.relative_width <= 1.0:
            raise InvalidInput(
                f"ouvertures[{self.id}].largeur_rel",
                f"must be in ]0, 1], got {self.relative_width}",
            )

    def segment_absolu(self, mur: Wall) -> tuple[Point, Point]:
        """Dériver les deux extrémités de la baie sur ``mur``.

        Parameters
        ----------
        mur : Mur
            Le mur portant cette ouverture ; son ``id`` doit valoir ``self.wall_id``.

        Returns
        -------
        tuple of Point
            Extrémités de la baie, en coordonnées absolues.

        Raises
        ------
        InvariantViolation
            Si ``mur.id`` ne correspond pas à ``self.wall_id``.

        Complexity
        ----------
        O(1).

        Examples
        --------
        >>> from archlux.types import Mur, Ouverture
        >>> mur = Mur(id="m", a=(0.0, 0.0), b=(10.0, 0.0))
        >>> Ouverture(id="f", wall_id="m", s=0.5, relative_width=0.2).segment_absolu(mur)
        ((4.0, 0.0), (6.0, 0.0))
        """
        if mur.id != self.wall_id:
            raise InvariantViolation(
                (f"ouverture {self.id} portée par {self.wall_id}, dérivée sur {mur.id}",)
            )
        (ax, ay), (bx, by) = mur.a, mur.b
        longueur = mur.longueur
        # Direction unitaire du mur ; un mur dégénéré rendrait une division par zéro,
        # ce que la garde ci-dessous transforme en invariant violé plutôt qu'en NaN.
        if longueur == 0.0:
            raise InvariantViolation((f"mur {mur.id} de longueur nulle",))
        ux, uy = (bx - ax) / longueur, (by - ay) / longueur
        cx, cy = ax + (bx - ax) * self.s, ay + (by - ay) * self.s
        demi = self.relative_width * longueur / 2.0
        return ((cx - demi * ux, cy - demi * uy), (cx + demi * ux, cy + demi * uy))


@dataclass(frozen=True, slots=True)
class Plan:
    """Un plan d'appartement, proposé ou légalisé.

    Un plan **légalisé** porte toujours son ``certificat`` ; un plan proposé ne l'a
    jamais. Le champ est donc le marqueur de l'état du plan, pas une décoration.

    ``trace`` n'est renseigné que si ``legalize(..., trace=True)`` : c'est la suite
    Frank-Wolfe, **non sérialisée** (elle n'appartient pas au schéma JSON).
    """

    rooms: tuple[Room, ...]
    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()
    outline: tuple[Point, ...] = ()
    certificate: Certificate | None = None
    # Typé ``object`` à dessein : ``solve.Trace`` vivrait une arête ``types → solve``,
    # interdite. La trace n'est pas sérialisée ; seuls les appelants ``trace=True``
    # la consomment.
    # ``compare=False``: the trace is a diagnostic, not part of the plan's identity. With
    # it in the comparison, ``hash(plan)`` failed on the trace's arrays.
    trace: object | None = field(default=None, compare=False, repr=False)

    @property
    def ids_pieces(self) -> tuple[str, ...]:
        """Identifiants de pièces, **triés** — garantit le déterminisme."""
        return tuple(sorted(p.id for p in self.rooms))

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
        InvariantViolation
            Le fichier ne respecte pas le schéma déclaré.
        """
        from archlux.io.json_io import charger

        return charger(chemin)

    def to_json(self, chemin: Path | str) -> None:
        """Écrire ce plan en JSON, clés triées, encodage UTF-8."""
        from archlux.io.json_io import ecrire

        ecrire(self, chemin)

    def to_dxf(self, chemin: Path | str) -> None:
        """Write the rooms as ``LWPOLYLINE`` and the walls as ``LINE`` in a DXF file.

        Facade over :func:`archlux.export.dxf.to_dxf`, by local import, like
        :meth:`from_json` (ADR-5 exemption).

        Raises
        ------
        InvariantViolation
            The plan has a blocking geometric pathology (overlap, gap...).
        """
        from archlux.export import to_dxf

        to_dxf(self, chemin)

    def to_ifc(self, chemin: Path | str, *, validate: bool = True) -> RapportExport:
        """Write the plan as IFC4 and return the report of the export.

        Facade over :func:`archlux.export.ifc.to_ifc`. With ``validate`` (default), a
        pathological plan is not written: the report says why, nothing is raised.
        """
        from archlux.export import to_ifc

        return to_ifc(self, chemin, validate=validate)

    def to_svg(self, chemin: Path | str, *, titre: str = "", walls: tuple[Wall, ...] = ()) -> None:
        """Draw the plan as a standalone SVG file, valid or not (the diagnostic use).

        Facade over :func:`archlux.export.svg.rendre` (exported as ``render_svg``).
        ``walls`` adds walls to draw, typically ``ctx.structure.load_bearing_walls``.
        """
        from archlux.export import render_svg

        Path(chemin).write_text(render_svg(self, titre=titre, walls=walls), encoding="utf-8")


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
class Regulation:
    """Seuils réglementaires : surfaces et largeurs minimales par type de pièce.

    Un référentiel est **une donnée**, pas du code : changer de réglementation ne doit
    jamais demander de modifier ``geom`` ou ``lmo``.
    """

    min_areas: tuple[tuple[str, float], ...]
    min_width: float = 1.80

    def min_area(self, type_piece: str) -> float:
        """Surface minimale exigée pour ``type_piece``, en mètres carrés.

        Parameters
        ----------
        type_piece : str
            Catégorie de programme, telle que portée par :attr:`Room.type`.

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
        for type_connu, seuil in self.min_areas:
            if type_connu == type_piece:
                return seuil
        return 0.0


@dataclass(frozen=True, slots=True)
class Structure:
    """Structure porteuse : ce que le solveur n'a pas le droit de déplacer."""

    load_bearing_walls: tuple[Wall, ...]
    columns: tuple[Point, ...] = ()


@dataclass(frozen=True, slots=True)
class Context:
    """Tout ce qui n'est pas le plan : structure, orientation, contour, référentiel.

    Séparer ``Plan`` et ``Context`` est ce qui permet à ``legalize`` d'avoir deux
    arguments et non douze, et rend le contexte réutilisable sur un lot de plans.
    """

    structure: Structure
    orientation: Orientation
    regulation: Regulation
    program: tuple[str, ...] = ()
    outline: tuple[Point, ...] = field(default=(), kw_only=True)
    """Outline of the site. Empty means "the outline of the plan": ``legalize`` takes
    ``plan.outline`` then (an outline given here wins over the plan's)."""


# ======================================================================================
# Certificat — les deux garanties, séparées par construction
# ======================================================================================


@dataclass(frozen=True, slots=True)
class GeometricProof:
    """Garantie **exacte**, vérifiée indépendamment du solveur.

    Ce type ne contient **aucun champ de probabilité** et ne doit jamais en contenir.
    C'est la thèse du projet inscrite dans le système de types : une preuve et une
    prédiction ne sont pas de même nature, et rien ne doit permettre de les mélanger.
    """

    valid: bool
    overlap: bool
    gaps: bool
    areas_ok: bool
    structure_kept: bool
    max_displacement: float
    violations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """A valid proof reports no fault; a displacement is never negative or NaN.

        ``inf`` is allowed: an unbounded displacement is how an invalid proof reports a
        NaN reference.
        """
        if not self.max_displacement >= 0.0:
            raise InvalidInput("max_displacement", f"must be >= 0, got {self.max_displacement}")
        if self.valid and (
            self.overlap
            or self.gaps
            or not self.areas_ok
            or not self.structure_kept
            or self.violations
        ):
            raise InvalidInput(
                "valid", "a valid proof cannot report an overlap, a gap or any violation"
            )


Regime = Literal["exchangeable", "selected"]
"""Under which assumption a conformal bound was computed (PLAN.md batch 1.6).

- ``"exchangeable"``: the plan is exchangeable with the calibration set (for example a
  held-out plan). The nominal coverage ``1 - alpha`` is guaranteed, marginally.
- ``"selected"``: the plan was chosen by the optimizer to maximize the prediction.
  Exchangeability is broken twice, by distribution shift and by the winner's curse (the
  argmax goes where the surrogate overestimates), so the nominal coverage is **not**
  guaranteed until the chosen plan is re-evaluated by the oracle (AUDIT.md §5.3).
"""

REGIMES: tuple[Regime, ...] = ("exchangeable", "selected")


@dataclass(frozen=True, slots=True)
class PerformanceBound:
    """Garantie **probabiliste** : intervalle à couverture ``≥ 1 − α``.

    ``couverture`` et ``n_calibration`` sont obligatoires : une borne conforme sans son
    niveau de couverture ni sa taille de calibration est invérifiable, donc sans valeur.
    ``regime`` is mandatory for the same reason: a coverage computed for an exchangeable
    plan does not hold for a plan the optimizer selected (:data:`Regime`).
    """

    indicator: Indicateur
    value: float
    lower: float
    upper: float
    coverage: float
    n_calibration: int
    regime: Regime

    def __post_init__(self) -> None:
        """Refuse a bound without calibration, an out-of-range coverage or regime."""
        if self.n_calibration < 1:
            raise InvariantViolation(("n_calibration doit être ≥ 1",))
        if not 0.0 < self.coverage <= 1.0:
            raise InvariantViolation((f"couverture hors ]0, 1] : {self.coverage}",))
        if self.regime not in REGIMES:
            raise InvariantViolation((f"unknown regime {self.regime!r}, expected {REGIMES}",))
        if not self.lower <= self.upper:
            raise InvariantViolation((f"inverted interval: {self.lower} > {self.upper}",))

    @property
    def coverage_guaranteed(self) -> bool:
        """True only when the nominal coverage holds: an exchangeable plan."""
        return self.regime == "exchangeable"


@dataclass(frozen=True, slots=True)
class ModelTrace:
    """Empreinte du modèle et taille de calibration — champs du manifeste de banc.

    ``poids`` est une empreinte (SHA), jamais le tenseur lui-même.
    """

    weights_fingerprint: str
    calibration_n: int
    alpha: float

    def __post_init__(self) -> None:
        """Valider empreinte, taille de calibration et niveau α."""
        if not self.weights_fingerprint:
            raise InvariantViolation(("empreinte de poids obligatoire",))
        if self.calibration_n < 1:
            raise InvariantViolation(("calibration_n doit être ≥ 1",))
        if not 0.0 < self.alpha < 1.0:
            raise InvariantViolation((f"alpha hors ]0, 1[ : {self.alpha}",))

    def __getitem__(self, cle: str) -> str | int | float:
        """Accès dictionnaire pour les assertions de manifeste (`MILESTONE-6`)."""
        try:
            return getattr(self, cle)  # type: ignore[no-any-return]
        except AttributeError as exc:
            raise KeyError(cle) from exc


@dataclass(frozen=True, slots=True)
class Manifest:
    """Trace de reproductibilité émise à chaque exécution, sans exception.

    Les champs sont des tuples de paires et non des ``dict`` : le manifeste est gelé et
    doit se sérialiser dans un ordre stable, sinon son empreinte n'est pas reproductible.
    """

    version: str
    timestamp: str
    seed: int
    data_fingerprint: str | None = None
    split: str | None = None
    environment: tuple[tuple[str, str], ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()
    model: ModelTrace | None = None


@dataclass(frozen=True, slots=True)
class Certificate:
    """Preuve exacte + borne probabiliste optionnelle + diagnostic dual.

    ``performance`` vaut ``None`` en légalisation classique : il n'y a alors rien de
    probabiliste à affirmer, et le certificat doit le dire plutôt que de le suggérer.

    Attributes
    ----------
    duaux : tuple of (str, float)
        Prix duaux **déjà traduits** via ``Polytope.origines`` : ``("mur porteur axe 3",
        4.1)``. Jamais un indice de ligne nu.
    """

    geometry: GeometricProof
    performance: PerformanceBound | None = None
    duals: tuple[tuple[str, float], ...] = ()
    manifest: Manifest | None = None

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


DEPRECATED_NAMES = {
    "Piece": "Room",
    "Mur": "Wall",
    "Ouverture": "Opening",
    "Contexte": "Context",
    "Referentiel": "Regulation",
    "Certificat": "Certificate",
    "PreuveGeometrique": "GeometricProof",
    "BornePerformance": "PerformanceBound",
    "Manifeste": "Manifest",
    "ModeleTrace": "ModelTrace",
}
"""Former French names of the model classes, kept as deprecated aliases until 1.0.0 (ADR 0001,
PLAN.md 3.9 wave 2). Not part of ``__all__``."""

__getattr__ = lazy_aliases(
    __name__,
    {old: Alias(globals()[new], f"archlux.types.{new}") for old, new in DEPRECATED_NAMES.items()},
)
