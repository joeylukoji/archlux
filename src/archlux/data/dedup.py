"""Geometric fingerprint and Hausdorff distance — deduplicate before splitting."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from shapely.geometry import box
from shapely.ops import unary_union

from archlux._deprecation import Alias, lazy_aliases

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
    """Hash the tiling rounded to the millimetre, rooms sorted by identifier."""
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
    """
    gauche = {p.id: p for p in a.rooms}
    droite = {p.id: p for p in b.rooms}
    if gauche.keys() != droite.keys():
        return hausdorff(a, b)
    if not gauche:
        # Two empty tilings are identical; ``max`` over an empty sequence would raise a
        # bare ``ValueError``, outside the project's error domain (§7).
        return 0.0
    return max(
        max(
            abs(gauche[i].x - droite[i].x),
            abs(gauche[i].y - droite[i].y),
            abs(gauche[i].w - droite[i].w),
            abs(gauche[i].h - droite[i].h),
        )
        for i in gauche
    )


def hausdorff(a: Plan, b: Plan) -> float:
    """Hausdorff distance between the unions of rectangles, in metres."""
    ua = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in a.rooms])
    ub = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in b.rooms])
    return float(ua.hausdorff_distance(ub))


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
    """
    empreintes = [geometric_fingerprint(plan) for _, plan in plans]
    paires: list[tuple[str, str]] = []
    for i, (ida, pa) in enumerate(plans):
        for decalage, (idb, pb) in enumerate(plans[i + 1 :]):
            j = i + 1 + decalage
            if empreintes[i] == empreintes[j] or side_distance(pa, pb) <= threshold:
                paires.append((ida, idb) if ida < idb else (idb, ida))
    return tuple(paires)


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
