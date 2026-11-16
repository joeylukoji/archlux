"""Functional checks, kept apart from the geometric certificate (AUDIT section 3).

A certified-valid plan has no overlap, no gap and its minimum areas: that is geometry,
not a usable dwelling. This module answers a few functional questions the model can
decide from rectangles, walls and openings, and says plainly which ones it cannot:

- **topology**: every room reaches every other through shared walls at least one door
  wide (a usable circulation graph);
- **required adjacencies**: given pairs of room types share such a wall;
- **openings**: every opening lies on an exterior wall and fits inside it;
- **daylight access**: every habitable room has a stretch of facade;
- **program**: every room type of ``ctx.program`` is present.

None of these is part of :class:`~archlux.types.GeometricProof`; a failure here never
turns a certified plan into an invalid one, it is reported next to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from archlux.tolerances import FUNCTIONAL_CONTACT_M as _TOL
from archlux.types import Context, Plan, Point, Room, Wall

__all__ = ["FUNCTIONAL_NOT_CHECKED", "FunctionalCheck", "FunctionalReport", "check_functional"]

FUNCTIONAL_NOT_CHECKED: tuple[str, ...] = (
    "door positions and swings (doors are not modelled; only wall stretches wide enough)",
    "accessibility clearances (turning circles, space beside beds)",
    "fire safety and evacuation distances",
    "ventilation and summer overheating",
    "structural soundness and constructibility",
    "the building code in force beyond the minimum areas and width",
)
"""What :func:`check_functional` never establishes."""

HABITABLE: tuple[str, ...] = ("living_room", "living", "bedroom", "kitchen")
"""Room types expected to have a facade (natural light and ventilation)."""

Status = Literal["satisfied", "violated", "not_applicable"]


@dataclass(frozen=True, slots=True)
class FunctionalCheck:
    """Verdict of one functional question.

    Attributes
    ----------
    id : str
        Stable identifier (``topology``, ``adjacencies``, ``openings``, ``facade``,
        ``program``).
    status : Status
        ``satisfied``, ``violated``, or ``not_applicable`` when the input lacks what the
        question needs (no opening, no program...).
    detail : str
        One sentence naming what fails, or what was checked.
    """

    id: str
    status: Status
    detail: str


@dataclass(frozen=True, slots=True)
class FunctionalReport:
    """All functional checks of one plan, and what they do not cover.

    Attributes
    ----------
    checks : tuple of FunctionalCheck
        One verdict per question.
    not_checked : tuple of str
        :data:`FUNCTIONAL_NOT_CHECKED`.
    """

    checks: tuple[FunctionalCheck, ...]
    not_checked: tuple[str, ...] = FUNCTIONAL_NOT_CHECKED

    @property
    def passed(self) -> bool:
        """Whether no check is violated.

        Returns
        -------
        bool
            ``True`` when every check is satisfied or not applicable.
        """
        return all(c.status != "violated" for c in self.checks)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Length of the intersection of ``[a0, a1]`` and ``[b0, b1]``.

    Parameters
    ----------
    a0, a1, b0, b1 : float
        Interval bounds, ``a0 <= a1`` and ``b0 <= b1``.

    Returns
    -------
    float
        The overlap, ``0`` when disjoint.
    """
    return max(0.0, min(a1, b1) - max(a0, b0))


def shared_wall(a: Room, b: Room) -> float:
    """Length of the wall two rooms share (touching sides), ``0`` if they do not touch.

    Parameters
    ----------
    a, b : Room
        Two rooms.

    Returns
    -------
    float
        The shared length in metres.
    """
    if abs(a.x + a.w - b.x) < _TOL or abs(b.x + b.w - a.x) < _TOL:
        return _overlap(a.y, a.y + a.h, b.y, b.y + b.h)
    if abs(a.y + a.h - b.y) < _TOL or abs(b.y + b.h - a.y) < _TOL:
        return _overlap(a.x, a.x + a.w, b.x, b.x + b.w)
    return 0.0


def _edges(outline: Sequence[Point]) -> list[tuple[Point, Point]]:
    """Edges of a closed outline.

    Parameters
    ----------
    outline : sequence of Point
        Vertices in order, the first not repeated.

    Returns
    -------
    list of tuple
        ``(a, b)`` per edge.
    """
    pts = [(float(x), float(y)) for x, y in outline]
    return [(p, pts[(k + 1) % len(pts)]) for k, p in enumerate(pts)]


def facade_length(room: Room, outline: Sequence[Point]) -> float:
    """Length of the room's sides lying on axis-aligned edges of the outline.

    Parameters
    ----------
    room : Room
        Room to measure.
    outline : sequence of Point
        Outline of the dwelling.

    Returns
    -------
    float
        Facade length in metres.
    """
    total = 0.0
    for (x0, y0), (x1, y1) in _edges(outline):
        if abs(y0 - y1) < _TOL and (abs(room.y - y0) < _TOL or abs(room.y + room.h - y0) < _TOL):
            total += _overlap(room.x, room.x + room.w, min(x0, x1), max(x0, x1))
        elif abs(x0 - x1) < _TOL and (abs(room.x - x0) < _TOL or abs(room.x + room.w - x0) < _TOL):
            total += _overlap(room.y, room.y + room.h, min(y0, y1), max(y0, y1))
    return total


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    """Whether ``p`` lies on the segment ``[a, b]``, up to the tolerance.

    Parameters
    ----------
    p, a, b : Point
        The point and the segment ends.

    Returns
    -------
    bool
        ``True`` if ``p`` is on the segment.
    """
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    inside = min(a[0], b[0]) - _TOL <= p[0] <= max(a[0], b[0]) + _TOL
    return abs(cross) < 1e-6 and inside and min(a[1], b[1]) - _TOL <= p[1] <= max(a[1], b[1]) + _TOL


def _exterior(wall: Wall, outline: Sequence[Point]) -> bool:
    """Whether the wall lies along one edge of the outline.

    Parameters
    ----------
    wall : Wall
        Wall to test.
    outline : sequence of Point
        Outline of the dwelling.

    Returns
    -------
    bool
        ``True`` if both wall ends lie on the same outline edge.
    """
    return any(_on_segment(wall.a, a, b) and _on_segment(wall.b, a, b) for a, b in _edges(outline))


def _components(rooms: Sequence[Room], door: float) -> list[set[str]]:
    """Connected groups of rooms through shared walls at least ``door`` wide.

    Parameters
    ----------
    rooms : sequence of Room
        Rooms of the plan.
    door : float
        Minimum shared length for a passage, in metres.

    Returns
    -------
    list of set of str
        Room ids per connected component.
    """
    groups: list[set[str]] = []
    for room in rooms:
        linked = [
            g for g in groups if any(shared_wall(room, o) >= door for o in rooms if o.id in g)
        ]
        merged = {room.id}.union(*linked)
        groups = [g for g in groups if g not in linked] + [merged]
    return groups


def _check_topology(plan: Plan, door: float) -> FunctionalCheck:
    """Topology check: one connected circulation graph.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    door : float
        Minimum passage width.

    Returns
    -------
    FunctionalCheck
        ``topology``.
    """
    groups = _components(plan.rooms, door)
    if len(groups) <= 1:
        return FunctionalCheck(
            "topology", "satisfied", f"every room reachable ({door:g} m passages)"
        )
    parts = " / ".join(",".join(sorted(g)) for g in sorted(groups, key=sorted))
    return FunctionalCheck("topology", "violated", f"{len(groups)} isolated groups: {parts}")


def _check_adjacencies(
    plan: Plan, pairs: Sequence[tuple[str, str]], door: float
) -> FunctionalCheck:
    """Required adjacencies between room types.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    pairs : sequence of tuple of str
        Room types that must share a wall at least ``door`` wide.
    door : float
        Minimum passage width.

    Returns
    -------
    FunctionalCheck
        ``adjacencies``.
    """
    if not pairs:
        return FunctionalCheck("adjacencies", "not_applicable", "no adjacency required")
    missing = [
        f"{a}-{b}"
        for a, b in pairs
        if not any(
            shared_wall(r, s) >= door
            for r in plan.rooms
            for s in plan.rooms
            if r.type == a and s.type == b and r.id != s.id
        )
    ]
    if missing:
        return FunctionalCheck("adjacencies", "violated", f"missing: {', '.join(missing)}")
    return FunctionalCheck("adjacencies", "satisfied", f"{len(pairs)} required adjacencies present")


def _check_openings(plan: Plan, outline: Sequence[Point]) -> FunctionalCheck:
    """Openings on exterior walls and inside their wall.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    outline : sequence of Point
        Outline of the dwelling.

    Returns
    -------
    FunctionalCheck
        ``openings``.
    """
    if not plan.openings:
        return FunctionalCheck("openings", "not_applicable", "no opening described")
    walls = {w.id: w for w in plan.walls}
    bad = []
    for o in plan.openings:
        wall = walls.get(o.wall_id)
        if wall is None:
            bad.append(f"{o.id}: wall {o.wall_id} missing")
        elif not _exterior(wall, outline):
            bad.append(f"{o.id}: on interior wall {wall.id}")
        elif o.s - o.relative_width / 2 < -_TOL or o.s + o.relative_width / 2 > 1 + _TOL:
            bad.append(f"{o.id}: overhangs wall {wall.id}")
    if bad:
        return FunctionalCheck("openings", "violated", "; ".join(bad))
    return FunctionalCheck("openings", "satisfied", f"{len(plan.openings)} openings on facades")


def _check_facade(
    plan: Plan, outline: Sequence[Point], habitable: Sequence[str]
) -> FunctionalCheck:
    """Habitable rooms with a stretch of facade.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    outline : sequence of Point
        Outline of the dwelling.
    habitable : sequence of str
        Room types that need a facade.

    Returns
    -------
    FunctionalCheck
        ``facade``.
    """
    rooms = [r for r in plan.rooms if r.type in habitable]
    if not rooms or not outline:
        return FunctionalCheck("facade", "not_applicable", "no habitable room or no outline")
    blind = sorted(r.id for r in rooms if facade_length(r, outline) < _TOL)
    if blind:
        return FunctionalCheck("facade", "violated", f"no facade: {', '.join(blind)}")
    return FunctionalCheck("facade", "satisfied", f"{len(rooms)} habitable rooms on a facade")


def _check_program(plan: Plan, program: Sequence[str]) -> FunctionalCheck:
    """Every room type of the program present.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    program : sequence of str
        Required room types.

    Returns
    -------
    FunctionalCheck
        ``program``.
    """
    if not program:
        return FunctionalCheck("program", "not_applicable", "no program given")
    missing = sorted(set(program) - {r.type for r in plan.rooms})
    if missing:
        return FunctionalCheck("program", "violated", f"missing room types: {', '.join(missing)}")
    return FunctionalCheck("program", "satisfied", "every room type of the program present")


def check_functional(
    plan: Plan,
    ctx: Context,
    *,
    door_width: float = 0.90,
    required_adjacencies: Sequence[tuple[str, str]] = (),
    habitable: Sequence[str] = HABITABLE,
) -> FunctionalReport:
    """Run the functional checks on a plan, apart from its geometric certificate.

    Parameters
    ----------
    plan : Plan
        Plan to check (typically the output of :func:`archlux.legalize`).
    ctx : Context
        Outline (``ctx.outline``, else ``plan.outline``) and program.
    door_width : float, optional
        Minimum shared wall for a passage, in metres (default 0.90).
    required_adjacencies : sequence of tuple of str, optional
        Pairs of room types that must share such a wall.
    habitable : sequence of str, optional
        Room types that need a facade (default :data:`HABITABLE`).

    Returns
    -------
    FunctionalReport
        One verdict per question, and :data:`FUNCTIONAL_NOT_CHECKED`.

    Examples
    --------
    >>> import archlux as ax
    >>> rooms = (ax.Room(id="a", type="bedroom", x=0, y=0, w=3, h=3),
    ...          ax.Room(id="b", type="living_room", x=3, y=0, w=3, h=3))
    >>> outline = ((0, 0), (6, 0), (6, 3), (0, 3))
    >>> ctx = ax.Context(ax.Structure(()), ax.Orientation(0.0), ax.Regulation((), 0.9),
    ...                  outline=outline)
    >>> check_functional(ax.Plan(rooms=rooms, outline=outline), ctx).passed
    True
    """
    outline = ctx.outline or plan.outline
    return FunctionalReport(
        checks=(
            _check_topology(plan, door_width),
            _check_adjacencies(plan, required_adjacencies, door_width),
            _check_openings(plan, outline),
            _check_facade(plan, outline, habitable),
            _check_program(plan, ctx.program),
        )
    )
