"""Relative order of rooms -> graph of separation constraints.

Translates "room A is left of room B" into the inequality ``x_A + w_A <= x_B``.

**Founding rule.** For every pair of rooms, **at least one** separation (left,
right, above, below) must exist. Without it, overlap remains possible and
no later added constraint can catch it.

Allowed dependencies: ``types``, ``errors``. Nothing else (`ARCHITECTURE.md` §5).

Derivation of the gap between rectangles, acyclicity and transitive reduction:
``docs/formules/ordre-relatif.md``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InconsistentOrder, MissingSeparation, UnsupportedInput
from archlux.tolerances import CONTACT_M, SNAP_M

if TYPE_CHECKING:
    from collections.abc import Sequence

    import networkx as nx

    from archlux.types import Plan, Room, Structure, Wall

__all__ = [
    "ConstraintGraph",
    "RelativeOrder",
    "WallSide",
    "build_graph",
    "deduce_order",
    "transitive_reduction",
]

Axe = Literal["horizontal", "vertical"]
Side = Literal["left", "right", "below", "above"]
_AXES: tuple[Axe, ...] = ("horizontal", "vertical")

TOLERANCE_CONTACT = CONTACT_M
"""Gap below which two rooms are considered touching, in meters (1 nanometer).

Without this tolerance, two rooms that touch exactly pass for overlapping:
``1.0 + 3.47`` is ``4.470000000000001`` in binary, not ``4.47``. The case is far from
rare: it occurs whenever a wall separates two adjacent rooms, that is, everywhere.
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
class RelativeOrder:
    """Partial order of the rooms on both axes.

    Attributes
    ----------
    horizontal : tuple of (str, str)
        ``(a, b)`` means "``a`` is left of ``b``".
    vertical : tuple of (str, str)
        ``(a, b)`` means "``a`` is below ``b``".
    rooms : tuple of str
        Identifiers involved, **sorted**, for a deterministic traversal.
    wall_sides : tuple of WallSide
        Side of every load-bearing wall each room stays on. Empty without structure.
    shared_sides : tuple of (str, tuple of str)
        ``(wall, members)``: the fused room whose members take one shared side of
        ``wall`` (two of them would otherwise take opposite sides). Empty if none.
    """

    horizontal: tuple[tuple[str, str], ...]
    vertical: tuple[tuple[str, str], ...]
    rooms: tuple[str, ...]
    wall_sides: tuple[WallSide, ...] = ()
    shared_sides: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class ConstraintGraph:
    """Two directed acyclic graphs, one per axis.

    The `dataclass` is frozen, but a ``DiGraph`` remains mutable: **treat both
    graphs as immutable**. :func:`transitive_reduction` returns a new object rather
    than modifying this one, and nothing in the project may add an edge afterwards:
    acyclicity and separation are validated at construction, once.
    """

    horizontal: nx.DiGraph
    vertical: nx.DiGraph

    def has_separation(self, a: str, b: str) -> bool:
        """Tell whether the pair ``(a, b)`` is separated on at least one axis.

        Parameters
        ----------
        a, b : str
            Room identifiers.

        Returns
        -------
        bool
            ``True`` if an edge links ``a`` and ``b`` in either graph, in either
            direction.

        Notes
        -----
        Query the **full** graph, before transitive reduction: after reduction, a pair
        separated by transitivity has no direct edge left. That is geometrically
        valid (the constraint remains implied), but this method would answer
        ``False``.

        Complexity
        ----------
        O(1) amortized.
        """
        return any(
            graphe.has_edge(a, b) or graphe.has_edge(b, a)
            for graphe in (self.horizontal, self.vertical)
        )

    def closure(self) -> frozenset[tuple[str, str, str]]:
        """Transitive closure of both graphs, as ``(axis, a, b)`` triplets.

        Returns
        -------
        frozenset of (str, str, str)
            All reachable pairs, per axis. This is the real order information,
            independent of whether an edge is explicit or implied.

        Complexity
        ----------
        O(n·m) per axis.
        """
        import networkx as nx  # lazy: 0.6 s at import, needed only by a first legalize

        triplets: set[tuple[str, str, str]] = set()
        for axe in _AXES:
            cloture = nx.transitive_closure_dag(getattr(self, axe))
            triplets.update((axe, a, b) for a, b in cloture.edges)
        return frozenset(triplets)


def deduce_order(
    plan: Plan,
    structure: Structure | None = None,
    groups: tuple[tuple[str, ...], ...] = (),
) -> RelativeOrder:
    """Extract the relative order of a proposed plan, by comparing centers.

    This is where the founding principle is applied: **the generator decides the order**.
    This function reads that decision and never questions it; the solver will then
    only change the dimensions.

    For each pair, the chosen axis is the one on which the rooms are **really
    disjoint**, the one with the larger gap if both are. Only failing that (the
    rooms overlap on both axes, the very defect ``legalize`` exists to fix) does the
    axis of the larger distance between centers decide.

    The order of the choice is not a style preference. Choosing the axis of the larger
    center distance while the rooms overlap on that axis produces a constraint that
    the original plan violates: ``legalize`` would move walls on a plan with no defect.

    The **direction** of the edge always follows the order of the centers, never that of
    the edges: this guarantees acyclicity, whichever axis is chosen for each pair.

    Parameters
    ----------
    plan : Plan
        Proposed plan, possibly invalid.
    structure : Structure, optional
        Load-bearing structure. Each wall is treated as a fixed obstacle: every room gets
        the side it stays on (:class:`WallSide`), read from the plan like the order
        between two rooms. A room that crosses a wall gets the smallest correction.
    groups : tuple of tuple of str, optional
        Sub-rectangles of one fused room (an L, see :mod:`archlux.geom.rectilinear`).
        Each takes its own side of a wall, unless two of them take **opposite** sides
        on one axis (one left of it, one right of it): only then can a seam between
        them land on the wall, inside the room. The group then takes one side, read
        from its bounding box; a half-plane holds the union exactly when it holds every
        member. The proof checks the union anyway (``certify.proof``). The test is on
        the whole group, not on the members that share a seam: a valid U or T wrapped
        around the end of a partial wall may still be refused, never a crossing
        accepted.

    Returns
    -------
    RelativeOrder
        Deduced partial order, ``rooms`` sorted, edges in deterministic order.

    Guarantees
    ----------
    - **Acyclic by construction.** On each axis, the edge follows the total order of the
      key ``(center coordinate, identifier)``; a subset of a total order
      cannot contain a cycle.
    - **Every pair separated**, since each pair receives exactly one edge.

    Complexity
    ----------
    O(n²) center comparisons, n = number of rooms.

    Examples
    --------
    >>> from archlux.geom.graph import deduce_order
    >>> from archlux.types import Room, Plan
    >>> left = Room(id="A", type="living_room", x=0.0, y=0.0, w=1.0, h=1.0)
    >>> right = Room(id="B", type="living_room", x=5.0, y=0.0, w=1.0, h=1.0)
    >>> deduce_order(Plan((left, right), (), (), ())).horizontal
    (('A', 'B'),)
    """
    par_id = {piece.id: piece for piece in plan.rooms}
    identifiants = sorted(par_id)
    horizontal, vertical = _pairwise_order(par_id, identifiants)

    envelope = _outline_envelope(plan)
    wall_sides: tuple[WallSide, ...] = ()
    shared_sides: tuple[tuple[str, tuple[str, ...]], ...] = ()
    if structure is not None:
        wall_sides, shared_sides = _wall_sides_and_groups(
            structure, groups, par_id, identifiants, envelope
        )
    return RelativeOrder(
        horizontal=tuple(horizontal),
        vertical=tuple(vertical),
        rooms=tuple(identifiants),
        wall_sides=wall_sides,
        shared_sides=shared_sides,
    )


def _pairwise_order(
    par_id: dict[str, Room], identifiants: list[str]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Horizontal and vertical edges for every pair, by comparing centers.

    Extracted from :func:`deduce_order` (PLAN.md phase 4, block 3): see that
    function's docstring for the axis-choice rule (real disjointness first, the
    larger center distance only if the rooms overlap on both axes).
    """
    horizontal: list[tuple[str, str]] = []
    vertical: list[tuple[str, str]] = []
    for id_a, id_b in itertools.combinations(identifiants, 2):
        a, b = par_id[id_a], par_id[id_b]
        (xa, ya), (xb, yb) = a.center, b.center
        # Gap between the two rooms on each axis: positive if they are disjoint.
        jeu_x = max(b.x - (a.x + a.w), a.x - (b.x + b.w))
        jeu_y = max(b.y - (a.y + a.h), a.y - (b.y + b.h))
        if jeu_x >= -TOLERANCE_CONTACT or jeu_y >= -TOLERANCE_CONTACT:
            horizontale = jeu_x >= jeu_y
        else:
            horizontale = abs(xb - xa) >= abs(yb - ya)
        if horizontale:
            # Key (center, id): a total order, so no cycle is possible on this axis.
            horizontal.append((id_a, id_b) if (xa, id_a) < (xb, id_b) else (id_b, id_a))
        else:
            vertical.append((id_a, id_b) if (ya, id_a) < (yb, id_b) else (id_b, id_a))
    return horizontal, vertical


def _outline_envelope(plan: Plan) -> Envelope | None:
    """Axis-aligned bounding box of the plan's outline, or ``None`` if it has none.

    Extracted from :func:`deduce_order` (PLAN.md phase 4, block 3).
    """
    if not plan.outline:
        return None
    xs = [x for x, _ in plan.outline]
    ys = [y for _, y in plan.outline]
    return (min(xs), min(ys), max(xs), max(ys))


def _wall_sides_and_groups(
    structure: Structure,
    groups: tuple[tuple[str, ...], ...],
    par_id: dict[str, Room],
    identifiants: list[str],
    envelope: Envelope | None,
) -> tuple[tuple[WallSide, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    """The wall side of every room, and the groups that had to share one.

    Extracted from :func:`deduce_order` (PLAN.md phase 4, block 3): see that
    function's ``groups`` parameter for why a fused room's sub-rectangles usually take
    their own side of a wall, and only share one when their choices straddle it.
    """
    walls = [
        m for m in sorted(structure.load_bearing_walls, key=lambda m: m.id) if m.length > SNAP_M
    ]
    for wall in walls:
        _check_axis_aligned(wall)
    sides = {
        (wall.id, room_id): _wall_side(par_id[room_id], wall, envelope)
        for wall in walls  # a point has no side; the proof ignores it too
        for room_id in identifiants
    }
    shared_sides: list[tuple[str, tuple[str, ...]]] = []
    for group in groups:
        shared_sides.extend(_assign_group_sides(group, walls, par_id, envelope, sides))
    wall_sides = tuple(sides[wall.id, room_id] for wall in walls for room_id in identifiants)
    return wall_sides, tuple(shared_sides)


def _group_members(group: tuple[str, ...], par_id: dict[str, Room]) -> list[Room] | None:
    """The rooms of ``group`` that exist in this plan, or ``None`` if fewer than two do.

    Extracted from :func:`_assign_group_sides` (PLAN.md phase 4, block 3).
    """
    members = [par_id[room_id] for room_id in group if room_id in par_id]
    return members if len(members) >= 2 else None


def _bounding_hull(members: list[Room]) -> Room:
    """Bounding box of ``members``, as a room of its own (PLAN.md phase 4, block 3)."""
    x0, y0 = min(m.x for m in members), min(m.y for m in members)
    x1, y1 = max(m.x + m.w for m in members), max(m.y + m.h for m in members)
    return replace(members[0], x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def _assign_group_sides(
    group: tuple[str, ...],
    walls: list[Wall],
    par_id: dict[str, Room],
    envelope: Envelope | None,
    sides: dict[tuple[str, str], WallSide],
) -> list[tuple[str, tuple[str, ...]]]:
    """One fused room's sub-rectangles: each its own wall side, unless they straddle it.

    Extracted from :func:`_wall_sides_and_groups` (PLAN.md phase 4, block 3). Members
    take their own side of a wall, read from their bounding box, unless two of them
    take **opposite** sides on that axis; only then do they share one, read from their
    hull. Mutates ``sides`` in place.

    Returns
    -------
    list of (str, tuple of str)
        One ``shared_sides`` entry per wall this group could not split compatibly;
        empty if the group has fewer than two members, or every wall left it
        compatible.
    """
    members = _group_members(group, par_id)
    if members is None:
        return []
    hull = _bounding_hull(members)
    member_ids = tuple(m.id for m in members)
    shared_sides: list[tuple[str, tuple[str, ...]]] = []
    for wall in walls:
        if not _assign_wall_side_for_group(wall, members, hull, envelope, sides):
            shared_sides.append((wall.id, member_ids))
    return shared_sides


def _assign_wall_side_for_group(
    wall: Wall,
    members: list[Room],
    hull: Room,
    envelope: Envelope | None,
    sides: dict[tuple[str, str], WallSide],
) -> bool:
    """One wall, one group: split it if the members' choices agree, else share the hull.

    Extracted from :func:`_assign_group_sides` (PLAN.md phase 4, block 3). Mutates
    ``sides`` in place.

    Returns
    -------
    bool
        ``True`` if the members split compatibly (each its own side); ``False`` if
        they had to share the hull's side instead.
    """
    # Among equally cheap sides, prefer an assignment without opposite sides.
    choices = [_wall_sides_by_penetration(m, wall, envelope) for m in members]
    compatible = _compatible_sides(choices)
    if compatible is not None:
        for ws in compatible:
            sides[wall.id, ws.room] = ws
        return True
    shared = _wall_side(hull, wall, envelope)
    for m in members:
        sides[wall.id, m.id] = replace(shared, room=m.id)
    return False


Envelope = tuple[float, float, float, float]
"""Axis-aligned bounding box ``(xmin, ymin, xmax, ymax)`` of the target outline."""


_QUADRANTS: tuple[tuple[Side, Side], ...] = (
    ("left", "below"),
    ("left", "above"),
    ("right", "below"),
    ("right", "above"),
)
"""Sets of sides without two opposite ones: any such set fits in one of these pairs."""


def _compatible_sides(choices: list[list[WallSide]]) -> list[WallSide] | None:
    """One side per member, no two opposite, each among the member's cheapest sides.

    Members on opposite sides of one wall could have their seam land on it. A set of
    sides without two opposite ones fits in one quadrant pair, so four candidates
    settle it in ``O(4 k)`` for ``k`` members; within a pair, each member keeps its
    cheapest side (the lists are sorted best first).
    """
    best = [options[0] for options in choices]
    if not _opposite({ws.side for ws in best}):
        return best
    for pair in _QUADRANTS:
        picked = [next((ws for ws in options if ws.side in pair), None) for options in choices]
        if all(ws is not None for ws in picked):
            return [ws for ws in picked if ws is not None]
    return None


def _opposite(taken: set[str]) -> bool:
    """Two members on opposite sides of one wall: their seam could land on it."""
    return {"left", "right"} <= taken or {"below", "above"} <= taken


def _check_axis_aligned(wall: Wall) -> None:
    """Refuse an oblique wall: no linear side constraint describes it exactly.

    Raises
    ------
    UnsupportedInput
        The wall is oblique.
    """
    (xa, ya), (xb, yb) = wall.a, wall.b
    if abs(xa - xb) > SNAP_M and abs(ya - yb) > SNAP_M:
        raise UnsupportedInput(
            f"load-bearing wall {wall.id} is oblique; only axis-aligned load-bearing "
            "walls can be kept exactly"
        )


def _wall_side(room: Room, wall: Wall, envelope: Envelope | None) -> WallSide:
    """Side of ``wall`` that ``room`` stays on: the half-plane it penetrates least.

    The wall is a fixed obstacle; each of its four half-planes (left of, right of,
    below the lower end, above the upper end) keeps the room off the segment. The one
    the room penetrates least is kept:

    - a room disjoint from the wall penetrates some half-plane negatively, and the
      least penetrated is the axis of the largest gap: the rule used between two rooms
      in :func:`deduce_order`;
    - a room crossing the wall gets the smallest correction, which may go *around* the
      end of a partial wall (1 cm over the end moves the room 1 cm, not across the wall).

    A half-plane with no room between the wall and the outline (``envelope``) is never
    kept: a full-span wall ends on the outline, so nothing fits beyond its ends.

    Raises
    ------
    UnsupportedInput
        The wall is oblique: no linear side constraint describes it exactly.
    """
    return _wall_sides_by_penetration(room, wall, envelope)[0]


def _wall_sides_by_penetration(room: Room, wall: Wall, envelope: Envelope | None) -> list[WallSide]:
    """The sides of :func:`_wall_side` that tie for the least penetration, best first.

    Raises
    ------
    UnsupportedInput
        The wall is oblique.
    """
    _check_axis_aligned(wall)
    (xa, ya), (xb, yb) = wall.a, wall.b
    x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
    ex0, ey0, ex1, ey1 = envelope if envelope is not None else (-math.inf,) * 2 + (math.inf,) * 2
    # (penetration, side, bound, room left between that half-plane's bound and the outline)
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
    """Assemble a directed acyclic graph for one axis, or raise."""
    import networkx as nx

    graphe = nx.DiGraph()
    graphe.add_nodes_from(sorted(noeuds))
    for a, b in aretes:
        if a not in graphe or b not in graphe:
            raise InconsistentOrder(cycle=(a, b), axis=axe)
        graphe.add_edge(a, b)
    if not nx.is_directed_acyclic_graph(graphe):
        cycle = nx.find_cycle(graphe)
        raise InconsistentOrder(cycle=tuple(a for a, _ in cycle), axis=axe)
    return graphe


@renamed_parameters({"pieces": "rooms"})
def build_graph(ordre: RelativeOrder, rooms: Sequence[str]) -> ConstraintGraph:
    """Assemble the two directed graphs and validate the order.

    Parameters
    ----------
    ordre : RelativeOrder
        Partial order, typically from :func:`deduce_order`.
    rooms : sequence of str
        **Authoritative** set of the expected rooms. An edge carrying an
        identifier absent from this set is refused: better to fail than to
        constrain a phantom room.

    Returns
    -------
    ConstraintGraph
        Horizontal and vertical graphs, acyclic, every pair separated.

    Raises
    ------
    InconsistentOrder
        A cycle exists on one of the axes ("A left of B left of A"), or an
        edge names an unknown room.
    MissingSeparation
        A pair of rooms is separated on no axis. This is the only error of this
        module that lets an overlap through if ignored.

    Guarantees
    ----------
    - Geometric: **exact**. If this function returns a graph, then every point
      satisfying its inequalities is free of overlap, for a fixed relative order.

    Complexity
    ----------
    O(n² + m), m = number of edges. The quadratic term comes from the separation
    check, which must examine all pairs.
    """
    graphe = ConstraintGraph(
        horizontal=_graphe_axe(ordre.horizontal, rooms, "horizontal"),
        vertical=_graphe_axe(ordre.vertical, rooms, "vertical"),
    )
    for a, b in itertools.combinations(sorted(rooms), 2):
        if not graphe.has_separation(a, b):
            raise MissingSeparation(pair=(a, b))
    return graphe


def transitive_reduction(g: ConstraintGraph) -> ConstraintGraph:
    """Remove the edges implied by transitivity, without changing the closure.

    **This step is not optional.** 15 rooms give ~210 raw constraints and
    ~30 after reduction. The solver is called 50 times per performance-driven
    legalization at milestone 3: the gain is multiplied by 50.

    Parameters
    ----------
    g : ConstraintGraph
        Acyclic graphs, as returned by :func:`build_graph`.

    Returns
    -------
    ConstraintGraph
        New graphs, with identical transitive closure, same nodes.

    Guarantees
    ----------
    - **No order information is lost**: ``closure()`` is unchanged. The removed
      constraints remain implied by those that stay.

    Complexity
    ----------
    O(n·m) per axis (``networkx.transitive_reduction``).
    """
    import networkx as nx

    reduits: dict[str, nx.DiGraph] = {}
    for axe in _AXES:
        origin: nx.DiGraph = getattr(g, axe)
        reduit = nx.transitive_reduction(origin)
        # `transitive_reduction` does not carry over isolated nodes: a room separated on
        # the other axis only would vanish from the graph, and the polytope would lose
        # its bounds.
        reduit.add_nodes_from(origin.nodes)
        reduits[axe] = reduit
    return ConstraintGraph(horizontal=reduits["horizontal"], vertical=reduits["vertical"])


__getattr__ = lazy_aliases(
    __name__,
    {
        "OrdreRelatif": Alias(RelativeOrder, "archlux.geom.graph.RelativeOrder"),
        "GrapheContraintes": Alias(ConstraintGraph, "archlux.geom.graph.ConstraintGraph"),
        "deduire_ordre": Alias(deduce_order, "archlux.geom.graph.deduce_order"),
        "construire_graphe": Alias(build_graph, "archlux.geom.graph.build_graph"),
        "reduction_transitive": Alias(
            transitive_reduction, "archlux.geom.graph.transitive_reduction"
        ),
    },
)
