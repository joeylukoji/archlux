"""Ordre relatif des pièces → graphe de contraintes de séparation.

Traduit « la pièce A est à gauche de la pièce B » en l'inégalité ``x_A + w_A ≤ x_B``.

**Règle fondatrice.** Pour chaque paire de pièces, **au moins une** séparation (gauche,
droite, dessus, dessous) doit exister. Sans elle, le chevauchement reste possible et
aucun ajout de contrainte ultérieur ne le rattrape.

Dépendances autorisées : ``types``, ``erreurs``. Rien d'autre (`ARCHITECTURE.md` §5).

Dérivation du jeu entre rectangles, acyclicité et réduction transitive :
``docs/formules/ordre-relatif.md``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

import networkx as nx

from archlux.erreurs import OrdreIncoherent, SeparationManquante, UnsupportedInput
from archlux.tolerances import CONTACT_M, SNAP_M

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.types import Mur, Piece, Plan, Structure

__all__ = [
    "GrapheContraintes",
    "OrdreRelatif",
    "WallSide",
    "construire_graphe",
    "deduire_ordre",
    "reduction_transitive",
]

Axe = Literal["horizontal", "vertical"]
Side = Literal["left", "right", "below", "above"]
_AXES: tuple[Axe, ...] = ("horizontal", "vertical")

TOLERANCE_CONTACT = CONTACT_M
"""Jeu en deçà duquel deux pièces sont réputées jointives, en mètres (1 nanomètre).

Sans cette tolérance, deux pièces qui se touchent exactement passent pour recouvrantes :
``1.0 + 3.47`` vaut ``4.470000000000001`` en binaire, pas ``4.47``. Le cas est loin d'être
rare — il survient dès qu'un mur sépare deux pièces adjacentes, c'est-à-dire partout.
"""


@dataclass(frozen=True, slots=True)
class WallSide:
    """A room stays on one side of a load-bearing wall, treated as a fixed obstacle.

    It is the relative order between a room and a wall, read from the proposed plan like
    the order between two rooms, and it becomes one linear row of the polytope:

    ============  ==================
    ``side``      constraint
    ============  ==================
    ``left``      ``x + w <= bound``
    ``right``     ``x >= bound``
    ``below``     ``y + h <= bound``
    ``above``     ``y >= bound``
    ============  ==================
    """

    room: str
    wall: str
    side: Side
    bound: float


@dataclass(frozen=True, slots=True)
class OrdreRelatif:
    """Ordre partiel des pièces sur les deux axes.

    Attributes
    ----------
    horizontal : tuple of (str, str)
        ``(a, b)`` signifie « ``a`` est à gauche de ``b`` ».
    vertical : tuple of (str, str)
        ``(a, b)`` signifie « ``a`` est en dessous de ``b`` ».
    pieces : tuple of str
        Identifiants concernés, **triés**, pour un parcours déterministe.
    wall_sides : tuple of WallSide
        Side of every load-bearing wall each room stays on. Empty without structure.
    """

    horizontal: tuple[tuple[str, str], ...]
    vertical: tuple[tuple[str, str], ...]
    pieces: tuple[str, ...]
    wall_sides: tuple[WallSide, ...] = ()


@dataclass(frozen=True, slots=True)
class GrapheContraintes:
    """Deux graphes orientés acycliques, un par axe.

    Le `dataclass` est gelé, mais un ``DiGraph`` reste mutable : **traiter les deux
    graphes comme immuables**. :func:`reduction_transitive` rend un nouvel objet plutôt
    que de modifier celui-ci, et rien dans le projet ne doit ajouter d'arête après coup —
    la validation d'acyclicité et de séparation a lieu à la construction, une fois.
    """

    horizontal: nx.DiGraph
    vertical: nx.DiGraph

    def a_separation(self, a: str, b: str) -> bool:
        """Dire si la paire ``(a, b)`` est séparée sur au moins un axe.

        Parameters
        ----------
        a, b : str
            Identifiants de pièces.

        Returns
        -------
        bool
            ``True`` si une arête relie ``a`` et ``b`` dans l'un des deux graphes, dans
            l'un ou l'autre sens.

        Notes
        -----
        À interroger sur le graphe **complet**, avant réduction transitive : après
        réduction, une paire séparée par transitivité n'a plus d'arête directe. C'est
        licite géométriquement — la contrainte reste impliquée — mais cette méthode
        répondrait ``False``.

        Complexity
        ----------
        O(1) amorti.
        """
        return any(
            graphe.has_edge(a, b) or graphe.has_edge(b, a)
            for graphe in (self.horizontal, self.vertical)
        )

    def fermeture(self) -> frozenset[tuple[str, str, str]]:
        """Fermeture transitive des deux graphes, en triplets ``(axe, a, b)``.

        Returns
        -------
        frozenset of (str, str, str)
            Tous les couples atteignables, par axe. C'est l'information d'ordre réelle,
            indépendante du fait qu'une arête soit explicite ou impliquée.

        Complexity
        ----------
        O(n·m) par axe.
        """
        triplets: set[tuple[str, str, str]] = set()
        for axe in _AXES:
            cloture = nx.transitive_closure_dag(getattr(self, axe))
            triplets.update((axe, a, b) for a, b in cloture.edges)
        return frozenset(triplets)


def deduire_ordre(
    plan: Plan,
    structure: Structure | None = None,
    groups: tuple[tuple[str, ...], ...] = (),
) -> OrdreRelatif:
    """Extraire l'ordre relatif d'un plan proposé, en comparant les centres.

    C'est ici qu'est appliqué le principe fondateur : **le générateur décide l'ordre**.
    Cette fonction lit cette décision et ne la remet jamais en cause ; le solveur ne
    changera ensuite que les dimensions.

    Pour chaque paire, l'axe retenu est celui sur lequel les pièces sont **réellement
    disjointes**, celui du plus grand jeu si les deux le sont. Ce n'est qu'à défaut —
    les pièces se chevauchent sur les deux axes, c'est-à-dire le défaut que ``legalize``
    existe pour corriger — que l'axe du plus grand écart entre centres tranche.

    L'ordre du choix n'est pas une préférence de style. Retenir l'axe du plus grand écart
    de centres alors que les pièces se recouvrent sur cet axe produit une contrainte que
    le plan d'origine viole : ``legalize`` déplacerait des murs sur un plan sans défaut.

    Le **sens** de l'arête suit toujours l'ordre des centres, jamais celui des bords :
    c'est ce qui garantit l'acyclicité, quel que soit l'axe retenu pour chaque paire.

    Parameters
    ----------
    plan : Plan
        Plan proposé, éventuellement invalide.
    structure : Structure, optional
        Load-bearing structure. Each wall is treated as a fixed obstacle: every room gets
        the side it stays on (:class:`WallSide`), read from the plan like the order
        between two rooms. A room that crosses a wall gets the smallest correction.
    groups : tuple of tuple of str, optional
        Sub-rectangles of one fused room (an L, see :mod:`archlux.geom.rectilineaire`).
        Each takes its own side of a wall, unless two of them take **opposite** sides
        on one axis (one left of it, one right of it): only then can a seam between
        them land on the wall, inside the room. The group then takes one side, read
        from its bounding box; a half-plane holds the union exactly when it holds every
        member. The proof checks the union anyway (``certify.proof``).

    Returns
    -------
    OrdreRelatif
        Ordre partiel déduit, ``pieces`` trié, arêtes en ordre déterministe.

    Guarantees
    ----------
    - **Acyclique par construction.** Sur chaque axe, l'arête suit l'ordre total de la
      clé ``(coordonnée du centre, identifiant)`` ; un sous-ensemble d'un ordre total ne
      peut pas contenir de cycle.
    - **Toute paire séparée**, puisque chaque paire reçoit exactement une arête.

    Complexity
    ----------
    O(n²) comparaisons de centres, n = nombre de pièces.

    Examples
    --------
    >>> from archlux.geom.graphe import deduire_ordre
    >>> from archlux.types import Piece, Plan
    >>> gauche = Piece(id="A", type="sejour", x=0.0, y=0.0, w=1.0, h=1.0)
    >>> droite = Piece(id="B", type="sejour", x=5.0, y=0.0, w=1.0, h=1.0)
    >>> deduire_ordre(Plan((gauche, droite), (), (), ())).horizontal
    (('A', 'B'),)
    """
    par_id = {piece.id: piece for piece in plan.pieces}
    identifiants = sorted(par_id)
    horizontal: list[tuple[str, str]] = []
    vertical: list[tuple[str, str]] = []

    for id_a, id_b in itertools.combinations(identifiants, 2):
        a, b = par_id[id_a], par_id[id_b]
        (xa, ya), (xb, yb) = a.centre, b.centre
        # Jeu entre les deux pièces sur chaque axe : positif si elles sont disjointes.
        jeu_x = max(b.x - (a.x + a.w), a.x - (b.x + b.w))
        jeu_y = max(b.y - (a.y + a.h), a.y - (b.y + b.h))
        if jeu_x >= -TOLERANCE_CONTACT or jeu_y >= -TOLERANCE_CONTACT:
            horizontale = jeu_x >= jeu_y
        else:
            horizontale = abs(xb - xa) >= abs(yb - ya)
        if horizontale:
            # Clé (centre, id) : un ordre total, donc aucun cycle possible sur cet axe.
            horizontal.append((id_a, id_b) if (xa, id_a) < (xb, id_b) else (id_b, id_a))
        else:
            vertical.append((id_a, id_b) if (ya, id_a) < (yb, id_b) else (id_b, id_a))

    envelope: Envelope | None = None
    if plan.contour:
        xs = [x for x, _ in plan.contour]
        ys = [y for _, y in plan.contour]
        envelope = (min(xs), min(ys), max(xs), max(ys))
    wall_sides: tuple[WallSide, ...] = ()
    if structure is not None:
        walls = [
            m for m in sorted(structure.murs_porteurs, key=lambda m: m.id) if m.longueur > SNAP_M
        ]
        sides = {
            (wall.id, room_id): _wall_side(par_id[room_id], wall, envelope)
            for wall in walls  # a point has no side; the proof ignores it too
            for room_id in identifiants
        }
        for group in groups:
            members = [par_id[room_id] for room_id in group if room_id in par_id]
            if len(members) < 2:
                continue
            x0, y0 = min(m.x for m in members), min(m.y for m in members)
            x1, y1 = max(m.x + m.w for m in members), max(m.y + m.h for m in members)
            hull = replace(members[0], x=x0, y=y0, w=x1 - x0, h=y1 - y0)
            for wall in walls:
                # Among equally cheap sides, prefer an assignment without opposite sides.
                choices = [_wall_sides_by_penetration(m, wall, envelope) for m in members]
                compatible = next(
                    (
                        combo
                        for combo in itertools.product(*choices)
                        if not _opposite({ws.side for ws in combo})
                    ),
                    None,
                )
                if compatible is not None:
                    for ws in compatible:
                        sides[wall.id, ws.room] = ws
                else:
                    shared = _wall_side(hull, wall, envelope)
                    for m in members:
                        sides[wall.id, m.id] = replace(shared, room=m.id)
        wall_sides = tuple(sides[wall.id, room_id] for wall in walls for room_id in identifiants)
    return OrdreRelatif(
        horizontal=tuple(horizontal),
        vertical=tuple(vertical),
        pieces=tuple(identifiants),
        wall_sides=wall_sides,
    )


Envelope = tuple[float, float, float, float]
"""Axis-aligned bounding box ``(xmin, ymin, xmax, ymax)`` of the target outline."""


def _opposite(taken: set[str]) -> bool:
    """Two members on opposite sides of one wall: their seam could land on it."""
    return {"left", "right"} <= taken or {"below", "above"} <= taken


def _wall_side(room: Piece, wall: Mur, envelope: Envelope | None) -> WallSide:
    """Side of ``wall`` that ``room`` stays on: the half-plane it penetrates least.

    The wall is a fixed obstacle; each of its four half-planes (left of, right of,
    below the lower end, above the upper end) keeps the room off the segment. The one
    the room penetrates least is kept:

    - a room disjoint from the wall penetrates some half-plane negatively, and the
      least penetrated is the axis of the largest gap: the rule used between two rooms
      in :func:`deduire_ordre`;
    - a room crossing the wall gets the smallest correction, which may go *around* the
      end of a partial wall (1 cm over the end moves the room 1 cm, not across the wall).

    A half-plane with no room between the wall and the outline (``envelope``) is never
    kept: a full-span wall ends on the outline, so nothing fits beyond its ends.

    Raises
    ------
    UnsupportedInput
        The wall is oblique: no linear side constraint describes it exactly.
    """
    (xa, ya), (xb, yb) = wall.a, wall.b
    vertical, horizontal = abs(xa - xb) <= SNAP_M, abs(ya - yb) <= SNAP_M
    if not (vertical or horizontal):
        raise UnsupportedInput(
            f"load-bearing wall {wall.id} is oblique; only axis-aligned load-bearing "
            "walls can be kept exactly"
        )
    x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
    ex0, ey0, ex1, ey1 = envelope if envelope is not None else (-math.inf,) * 2 + (math.inf,) * 2
    # (penetration, side, bound, room left between that half-plane's bound and the outline)
    options: list[tuple[float, Side, float, float]] = [
        (room.x + room.w - x0, "left", x0, x0 - ex0),
        (x1 - room.x, "right", x1, ex1 - x1),
        (room.y + room.h - y0, "below", y0, y0 - ey0),
        (y1 - room.y, "above", y1, ey1 - y1),
    ]
    return _wall_sides_by_penetration(room, wall, envelope)[0]


def _wall_sides_by_penetration(
    room: Piece, wall: Mur, envelope: Envelope | None
) -> list[WallSide]:
    """The sides of :func:`_wall_side` that tie for the least penetration, best first."""
    (xa, ya), (xb, yb) = wall.a, wall.b
    x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
    ex0, ey0, ex1, ey1 = envelope if envelope is not None else (-math.inf,) * 2 + (math.inf,) * 2
    options: list[tuple[float, Side, float, float]] = [
        (room.x + room.w - x0, "left", x0, x0 - ex0),
        (x1 - room.x, "right", x1, ex1 - x1),
        (room.y + room.h - y0, "below", y0, y0 - ey0),
        (y1 - room.y, "above", y1, ey1 - y1),
    ]
    reachable = [option for option in options if option[3] > CONTACT_M] or options
    best = min(option[0] for option in reachable)
    return [
        WallSide(room=room.id, wall=wall.id, side=side, bound=bound)
        for penetration, side, bound, _ in sorted(reachable, key=lambda option: option[0])
        if penetration <= best + CONTACT_M
    ]


def _graphe_axe(aretes: tuple[tuple[str, str], ...], noeuds: Sequence[str], axe: Axe) -> nx.DiGraph:
    """Assembler un graphe orienté acyclique pour un axe, ou lever."""
    graphe = nx.DiGraph()
    graphe.add_nodes_from(sorted(noeuds))
    for a, b in aretes:
        if a not in graphe or b not in graphe:
            raise OrdreIncoherent(cycle=(a, b), axe=axe)
        graphe.add_edge(a, b)
    if not nx.is_directed_acyclic_graph(graphe):
        cycle = nx.find_cycle(graphe)
        raise OrdreIncoherent(cycle=tuple(a for a, _ in cycle), axe=axe)
    return graphe


def construire_graphe(ordre: OrdreRelatif, pieces: Sequence[str]) -> GrapheContraintes:
    """Assembler les deux graphes orientés et valider l'ordre.

    Parameters
    ----------
    ordre : OrdreRelatif
        Ordre partiel, typiquement issu de :func:`deduire_ordre`.
    pieces : sequence of str
        Ensemble **faisant autorité** des pièces attendues. Une arête portant un
        identifiant absent de cet ensemble est refusée : mieux vaut échouer que
        contraindre une pièce fantôme.

    Returns
    -------
    GrapheContraintes
        Graphes horizontal et vertical, acycliques, toutes paires séparées.

    Raises
    ------
    OrdreIncoherent
        Un cycle existe sur l'un des axes (« A à gauche de B à gauche de A »), ou une
        arête désigne une pièce inconnue.
    SeparationManquante
        Une paire de pièces n'est séparée sur aucun axe. C'est la seule erreur de ce
        module qui laisse passer un chevauchement si on l'ignore.

    Guarantees
    ----------
    - Géométrique : **exacte**. Si cette fonction rend un graphe, alors tout point
      satisfaisant ses inégalités est sans chevauchement — à ordre relatif fixé.

    Complexity
    ----------
    O(n² + m), m = nombre d'arêtes. Le terme quadratique vient du contrôle de
    séparation, qui doit examiner toutes les paires.
    """
    graphe = GrapheContraintes(
        horizontal=_graphe_axe(ordre.horizontal, pieces, "horizontal"),
        vertical=_graphe_axe(ordre.vertical, pieces, "vertical"),
    )
    for a, b in itertools.combinations(sorted(pieces), 2):
        if not graphe.a_separation(a, b):
            raise SeparationManquante(paire=(a, b))
    return graphe


def reduction_transitive(g: GrapheContraintes) -> GrapheContraintes:
    """Retirer les arêtes impliquées par transitivité, sans changer la fermeture.

    **Cette étape n'est pas optionnelle.** 15 pièces donnent ~210 contraintes brutes et
    ~30 après réduction. Le solveur est appelé 50 fois par légalisation performantielle
    au jalon 3 : le gain se multiplie par 50.

    Parameters
    ----------
    g : GrapheContraintes
        Graphes acycliques, tels que rendus par :func:`construire_graphe`.

    Returns
    -------
    GrapheContraintes
        Nouveaux graphes, de fermeture transitive identique, mêmes nœuds.

    Guarantees
    ----------
    - **Aucune information d'ordre n'est perdue** : ``fermeture()`` est inchangée. Les
      contraintes retirées restent impliquées par celles qui demeurent.

    Complexity
    ----------
    O(n·m) par axe (``networkx.transitive_reduction``).
    """
    reduits: dict[str, nx.DiGraph] = {}
    for axe in _AXES:
        origine: nx.DiGraph = getattr(g, axe)
        reduit = nx.transitive_reduction(origine)
        # `transitive_reduction` ne reporte pas les nœuds isolés : une pièce séparée sur
        # le seul autre axe disparaîtrait du graphe, et le polytope perdrait ses bornes.
        reduit.add_nodes_from(origine.nodes)
        reduits[axe] = reduit
    return GrapheContraintes(horizontal=reduits["horizontal"], vertical=reduits["vertical"])
