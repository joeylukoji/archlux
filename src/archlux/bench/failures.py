"""Break the B8 repair rates down by failure class, conditioning and program size.

AUDIT 2.3: the 740 generated plans are not summarized by one percentage. Each raw row
of ``j8_{etoile,plausible,divers}_raw.csv`` (tiling, repair budget 16) is mapped to the
user outcomes of :mod:`archlux.certify.outcome`; a repaired plan whose largest move
exceeds ``strong`` of its side counts as a strong deformation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

from archlux.export.wilson import wilson_interval

__all__ = ["CLASSES", "classify_row", "failure_table"]

CLASSES: tuple[str, ...] = (
    "repaired",
    "repaired_strong_deformation",
    "contradictory_constraints",
    "grid_budget_exceeded",
    "other",
)
"""Columns of :func:`failure_table`, in order."""

_STATUS = {"infaisable": "contradictory_constraints", "trame": "grid_budget_exceeded"}


def classify_row(row: Mapping[str, str], *, strong: float = 0.25) -> str:
    """Class of one raw B8 row.

    Parameters
    ----------
    row : mapping
        A row with ``status`` and ``relative_displacement``.
    strong : float, optional
        Relative displacement above which a repair is a strong deformation.

    Returns
    -------
    str
        One of :data:`CLASSES`.

    Examples
    --------
    >>> classify_row({"status": "ok", "relative_displacement": "0.43"})
    'repaired_strong_deformation'
    >>> classify_row({"status": "trame", "relative_displacement": ""})
    'grid_budget_exceeded'
    """
    if row["status"] == "ok":
        moved = float(row["relative_displacement"] or 0.0)
        return "repaired_strong_deformation" if moved > strong else "repaired"
    return _STATUS.get(row["status"], "other")


def failure_table(
    rows: Iterable[Mapping[str, str]], *, by: str, strong: float = 0.25
) -> list[tuple[str, int, dict[str, int], tuple[float, float]]]:
    """Counts per class, for each value of the column ``by``.

    Parameters
    ----------
    rows : iterable of mapping
        Raw rows, already filtered to one mode, budget and minimum width.
    by : str
        Grouping column (``graph``, ``n_rooms``...).
    strong : float, optional
        See :func:`classify_row`.

    Returns
    -------
    list of tuple
        ``(group, n, counts per class, Wilson 95 % interval of the repaired share)``,
        sorted by group; "repaired" counts both repaired classes.
    """
    groups: dict[str, Counter[str]] = {}
    for row in rows:
        groups.setdefault(row[by], Counter())[classify_row(row, strong=strong)] += 1
    out = []
    for group in sorted(groups, key=lambda g: (len(g), g)):
        counts = groups[group]
        n = sum(counts.values())
        repaired = counts["repaired"] + counts["repaired_strong_deformation"]
        out.append((group, n, {c: counts[c] for c in CLASSES}, wilson_interval(repaired, n)))
    return out
