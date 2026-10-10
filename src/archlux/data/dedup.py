"""Geometric fingerprint and Hausdorff distance — deduplicate before splitting."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from shapely.geometry import box
from shapely.ops import unary_union

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.types import Plan

__all__ = [
    "HAUSDORFF_THRESHOLD_M",
    "geometric_fingerprint",
    "hausdorff",
    "near_duplicate_pairs",
    "side_distance",
]

HAUSDORFF_THRESHOLD_M = 0.02
"""Threshold in metres: two tilings closer than this are the same unit (`MILESTONE-4.md`)."""


def geometric_fingerprint(plan: Plan) -> str:
    """Hash the tiling rounded to the millimetre, rooms sorted by identifier.

    Parameters
    ----------
    plan
        Plan to fingerprint.

    Returns
    -------
    str
        Hex BLAKE2b (128-bit) digest of the rounded tiling.
    """
    rooms = tuple(
        (
            p.id,
            p.type,
            round(p.x, 3),
            round(p.y, 3),
            round(p.w, 3),
            round(p.h, 3),
        )
        for p in sorted(plan.rooms, key=lambda room: room.id)
    )
    return hashlib.blake2b(repr(rooms).encode(), digest_size=16).hexdigest()


def side_distance(a: Plan, b: Plan) -> float:
    """L-infinity gap between dimensions, rooms matched by identifier.

    The Hausdorff distance of the *unions* is zero for two tilings of the same
    outline: it does not detect a partition duplicate. It is the gap between
    the rectangles that matters for deduplicating before splitting.

    Parameters
    ----------
    a
        First plan.
    b
        Second plan.

    Returns
    -------
    float
        Largest dimension gap between rooms of the same identifier, in metres; the Hausdorff
        distance when the identifiers differ, zero for two empty plans.
    """
    left = {p.id: p for p in a.rooms}
    right = {p.id: p for p in b.rooms}
    if left.keys() != right.keys():
        return hausdorff(a, b)
    if not left:
        # Two empty tilings are identical; ``max`` over an empty sequence would raise a
        # bare ``ValueError``, outside the project's error domain (§7).
        return 0.0
    return max(
        max(
            abs(left[i].x - right[i].x),
            abs(left[i].y - right[i].y),
            abs(left[i].w - right[i].w),
            abs(left[i].h - right[i].h),
        )
        for i in left
    )


def hausdorff(a: Plan, b: Plan) -> float:
    """Hausdorff distance between the unions of rectangles, in metres.

    Parameters
    ----------
    a
        First plan.
    b
        Second plan.

    Returns
    -------
    float
        Hausdorff distance between the two unions of rooms, in metres.
    """
    ua = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in a.rooms])
    ub = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in b.rooms])
    return float(ua.hausdorff_distance(ub))


@renamed_parameters({"seuil": "threshold"})
def near_duplicate_pairs(
    plans: Sequence[tuple[str, Plan]], *, threshold: float = HAUSDORFF_THRESHOLD_M
) -> tuple[tuple[str, str], ...]:
    """Pairs of identifiers whose dimension gap is under ``threshold``.

    The relation "gap <= threshold" is **not transitive**: ``a ~ b`` and ``b ~ c``
    do not imply ``a ~ c``. This function therefore returns the edges of the
    similarity graph, never classes. A caller that deduplicates must close these
    edges into connected components (union-find) before splitting, otherwise two
    members of the same chain can land on either side of a train/test boundary.

    Complexity
    ----------
    ``O(n^2)`` comparisons; fingerprints are computed **once per plan** (``O(n)``),
    not per pair.

    Parameters
    ----------
    plans
        ``(identifier, plan)`` pairs.
    threshold
        Largest dimension gap, in metres, still a near duplicate.

    Returns
    -------
    tuple of tuple of str
        The pairs of identifiers closer than ``threshold``.
    """
    fingerprints = [geometric_fingerprint(plan) for _, plan in plans]
    pairs: list[tuple[str, str]] = []
    for i, (ida, pa) in enumerate(plans):
        for offset, (idb, pb) in enumerate(plans[i + 1 :]):
            j = i + 1 + offset
            if fingerprints[i] == fingerprints[j] or side_distance(pa, pb) <= threshold:
                pairs.append((ida, idb) if ida < idb else (idb, ida))
    return tuple(pairs)


__getattr__ = lazy_aliases(
    __name__,
    {
        "empreinte_geometrique": Alias(
            geometric_fingerprint, "archlux.data.dedup.geometric_fingerprint"
        ),
        "distance_cotes": Alias(side_distance, "archlux.data.dedup.side_distance"),
        "paires_quasi_identiques": Alias(
            near_duplicate_pairs, "archlux.data.dedup.near_duplicate_pairs"
        ),
        "SEUIL_HAUSDORFF_M": Alias(
            HAUSDORFF_THRESHOLD_M, "archlux.data.dedup.HAUSDORFF_THRESHOLD_M"
        ),
    },
)
