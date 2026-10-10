"""A repair report an architect can read: room by room, in metres and square metres (PLAN.md 5.5).

The certificate (:mod:`archlux.certify.report`) states what was proved. This report says
what changed: each room's size before and after, its regulatory minimum and the margin
left, how far its walls moved, which rooms are too narrow, what limited the repair, and
what the regulation in use does not check. English or French, same content.

Examples
--------
>>> from archlux.types import Plan, Regulation, Room
>>> before = Plan(rooms=(Room(id="bed", type="bedroom", x=0.0, y=0.0, w=2.5, h=3.0),))
>>> after = Plan(rooms=(Room(id="bed", type="bedroom", x=0.0, y=0.0, w=3.0, h=3.0),))
>>> report = render_repair(before, after, Regulation((("bedroom", 9.0),), min_width=0.9))
>>> "7.50 m²" in report and "9.00 m²" in report
True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from archlux._version import __version__
from archlux.errors import InvalidInput
from archlux.tolerances import SNAP_M
from archlux.types import Plan, Regulation, Room

__all__ = ["RoomChange", "render_repair", "room_changes"]

Language = Literal["en", "fr"]

_WORDS: dict[str, dict[str, str]] = {
    "en": {
        "title": "PLAN REPAIR",
        "valid": "Verdict: valid (exact check)",
        "invalid": "Verdict: NOT valid",
        "uncertified": "Verdict: not certified (the plan carries no certificate)",
        "largest": "Largest wall move: {move} ({room})",
        "rooms": "ROOMS",
        "header": "{room:<24} {before:<23} {after:<23} {minimum:>9} {margin:>10} {move:>8}",
        "added": "added",
        "removed": "removed",
        "width_ok": "Widths: every room is at least {width} wide",
        "width_bad": "Widths: {count} room(s) narrower than {width}",
        "limits": "WHAT LIMITED THE REPAIR",
        "no_limit": "  nothing: no regulatory or structural constraint was binding",
        "not_checked": "NOT CHECKED BY THIS REGULATION",
        "nothing_listed": "  (nothing listed: check the regulation in force yourself)",
    },
    "fr": {
        "title": "CORRECTION DU PLAN",
        "valid": "Verdict : valide (vérification exacte)",
        "invalid": "Verdict : NON valide",
        "uncertified": "Verdict : non certifié (le plan ne porte pas de certificat)",
        "largest": "Plus grand déplacement de mur : {move} ({room})",
        "rooms": "PIÈCES",
        "header": "{room:<24} {before:<23} {after:<23} {minimum:>9} {margin:>10} {move:>8}",
        "added": "ajoutée",
        "removed": "supprimée",
        "width_ok": "Largeurs : chaque pièce fait au moins {width}",
        "width_bad": "Largeurs : {count} pièce(s) plus étroite(s) que {width}",
        "limits": "CE QUI A LIMITÉ LA CORRECTION (diagnostic du solveur, en anglais)",
        "no_limit": "  rien : aucune contrainte réglementaire ou structurelle n'était active",
        "not_checked": "NON VÉRIFIÉ PAR CETTE RÉGLEMENTATION",
        "nothing_listed": "  (rien de listé : vérifiez vous-même la réglementation en vigueur)",
    },
}


_COLUMNS: dict[str, dict[str, str]] = {
    "en": dict(
        room="room",
        before="before",
        after="after",
        minimum="minimum",
        margin="margin",
        move="moved",
    ),
    "fr": dict(
        room="pièce",
        before="avant",
        after="après",
        minimum="minimum",
        margin="marge",
        move="déplacé",
    ),
}
"""Headers of the room table, by language."""


@dataclass(frozen=True, slots=True)
class RoomChange:
    """One room before and after the repair.

    Attributes
    ----------
    id : str
        Room identifier.
    type : str
        Room type.
    before, after : Room or None
        The room in each plan; ``None`` where it does not exist.
    minimum : float
        Regulatory minimum area of its type, in m² (``0.0`` when unregulated).
    """

    id: str
    type: str
    before: Room | None
    after: Room | None
    minimum: float

    @property
    def moved(self) -> float:
        """Largest move of one of the room's four walls, in metres.

        Returns
        -------
        float
            ``0.0`` for a room added or removed.
        """
        if self.before is None or self.after is None:
            return 0.0
        b, a = self.before, self.after
        edges = ((b.x, a.x), (b.x + b.w, a.x + a.w), (b.y, a.y), (b.y + b.h, a.y + a.h))
        return max(abs(new - old) for old, new in edges)

    @property
    def margin(self) -> float | None:
        """Area above the minimum after the repair, in m²; negative when below.

        Returns
        -------
        float or None
            ``None`` for a removed room.
        """
        return None if self.after is None else self.after.area - self.minimum


def room_changes(before: Plan, after: Plan, regulation: Regulation) -> tuple[RoomChange, ...]:
    """Pair the rooms of two plans by identifier.

    Parameters
    ----------
    before, after : Plan
        The plan as proposed and as repaired.
    regulation : Regulation
        Gives each type's minimum area.

    Returns
    -------
    tuple of RoomChange
        One per identifier, sorted.
    """
    old = {room.id: room for room in before.rooms}
    new = {room.id: room for room in after.rooms}
    changes = []
    for room_id in sorted(old.keys() | new.keys()):
        room = new.get(room_id) or old[room_id]
        minimum = regulation.min_area(room.type)
        changes.append(RoomChange(room_id, room.type, old.get(room_id), new.get(room_id), minimum))
    return tuple(changes)


def _size(room: Room | None, missing: str) -> str:
    """``"4.20 x 3.50 = 14.70 m²"``, or ``missing``.

    Parameters
    ----------
    room
        The room, or ``None``.
    missing
        Text for a room that does not exist.

    Returns
    -------
    str
        The dimensions and area.
    """
    return missing if room is None else f"{room.w:.2f} x {room.h:.2f} = {room.area:.2f} m²"


def _row(change: RoomChange, words: dict[str, str]) -> str:
    """One line of the room table.

    Parameters
    ----------
    change
        The room.
    words
        Messages of the language.

    Returns
    -------
    str
        Name, sizes, minimum, margin and wall move.
    """
    margin = change.margin
    if margin is not None:
        margin = round(margin, 2) + 0.0  # no "-0.00": it would read as below the minimum
    return words["header"].format(
        room=f"{change.id} ({change.type})"[:24],
        before=_size(change.before, words["added"]),
        after=_size(change.after, words["removed"]),
        minimum=f"{change.minimum:.2f} m²" if change.minimum else "-",
        margin="-" if margin is None or not change.minimum else f"{margin:+.2f} m²",
        move=f"{change.moved:.2f} m",
    )


def _verdict(after: Plan, words: dict[str, str]) -> list[str]:
    """The verdict of the certificate, and its violations.

    Parameters
    ----------
    after
        The repaired plan.
    words
        Messages of the language.

    Returns
    -------
    list of str
        The verdict line, then one line per violation.
    """
    if after.certificate is None:
        return [words["uncertified"]]
    proof = after.certificate.geometry
    if proof.valid:
        return [words["valid"]]
    return [words["invalid"], *(f"  - {violation}" for violation in proof.violations)]


def _widths(after: Plan, regulation: Regulation, words: dict[str, str]) -> list[str]:
    """The width check: every room against ``regulation.min_width``.

    Parameters
    ----------
    after
        The repaired plan.
    regulation
        Gives the minimum width.
    words
        Messages of the language.

    Returns
    -------
    list of str
        One summary line, then one line per narrow room.
    """
    width = f"{regulation.min_width:.2f} m"
    narrow = [r for r in after.rooms if min(r.w, r.h) < regulation.min_width - SNAP_M]
    if not narrow:
        return [words["width_ok"].format(width=width)]
    return [
        words["width_bad"].format(count=len(narrow), width=width),
        *(f"  - {r.id}: {min(r.w, r.h):.2f} m" for r in narrow),
    ]


def render_repair(
    before: Plan,
    after: Plan,
    regulation: Regulation,
    *,
    lang: Language = "en",
    not_checked: tuple[str, ...] = (),
) -> str:
    """Report what the repair changed, room by room, in metres and square metres.

    Parameters
    ----------
    before : Plan
        The plan as proposed.
    after : Plan
        The plan as repaired, normally carrying its certificate.
    regulation : Regulation
        The regulation the repair enforced.
    lang : {"en", "fr"}, optional
        Language of the report.
    not_checked : tuple of str, optional
        Rules the regulation leaves unchecked, e.g. a preset's ``not_checked``.

    Returns
    -------
    str
        The report, verdict first.

    Raises
    ------
    InvalidInput
        ``lang`` is neither ``"en"`` nor ``"fr"``.
    """
    if lang not in _WORDS:
        raise InvalidInput("lang", f"unknown language {lang!r}", f"use one of {sorted(_WORDS)}")
    words = _WORDS[lang]
    changes = room_changes(before, after, regulation)
    lines = [f"{words['title']}                                archlux {__version__}", ""]
    lines += _verdict(after, words)
    if changes:
        largest = max(changes, key=lambda change: change.moved)
        lines.append(words["largest"].format(move=f"{largest.moved:.2f} m", room=largest.id))
    lines += ["", words["rooms"], words["header"].format(**_COLUMNS[lang])]
    lines += [_row(change, words) for change in changes]
    lines += ["", *_widths(after, regulation, words), "", words["limits"]]
    duals = after.certificate.duals if after.certificate else ()
    lines += [f"  {label}" for label, _ in duals] or [words["no_limit"]]
    lines += ["", words["not_checked"]]
    lines += [f"  - {rule}" for rule in not_checked] or [words["nothing_listed"]]
    return "\n".join(lines) + "\n"
