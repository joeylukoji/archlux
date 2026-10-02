"""Repair of a recovered grid: orphan-line consolidation and bounded partition repair.

Split from :mod:`archlux.geom.pavage` (PLAN.md phase 4, block 3). Both passes move
**indices only**, never a coordinate; :func:`archlux.geom.grid.deduce_grid` calls them.
See :mod:`archlux.geom.pavage` for the rationale (support of a line, repair budget).
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []


def _consolider(
    lignes: list[float],
    bords: list[tuple[int, int]],
    protegees: set[int],
    min_support: int,
) -> tuple[list[float], list[tuple[int, int]], set[int]]:
    """Absorb the **orphan** lines into their nearest neighbor.

    In a sound plan, an interior grid line is carried by several
    edges: a wall separates two rooms, so at least one edge on each side.
    Moving a room makes one edge leave its line and creates a new one,
    carried by it alone. The **support** (the number of edges carried) thus
    distinguishes the intended structure from the accident, without any metric
    tolerance having to be guessed.

    Absorption continues while an interior line of support ``< min_support`` remains,
    merging it with the nearest line, unless this **crushes a
    room**, that is, brings both of its edges onto the same line. This refusal is what
    keeps a narrow room from being absorbed by a tolerance that is too wide.

    Parameters
    ----------
    lignes : list of float
        Line positions, increasing.
    bords : list of (int, int)
        One ``(low_line, high_line)`` pair per room, on this axis.
    protegees : set of int
        Lines that are never absorbed: the outline edges.
    min_support : int
        Below this number of carried edges, an interior line is an orphan.

    Returns
    -------
    tuple
        ``(lignes, bords, protegees)`` reindexed, with no absorbable orphan line left.
    """
    while True:
        support: dict[int, int] = dict.fromkeys(range(len(lignes)), 0)
        for basse, haute in bords:
            support[basse] += 1
            support[haute] += 1
        candidates = sorted(
            (k for k, n in support.items() if n < min_support and k not in protegees),
            key=lambda k: (support[k], k),
        )
        fusion: tuple[int, int] | None = None
        for orpheline in candidates:
            voisines = sorted(
                (j for j in range(len(lignes)) if j != orpheline),
                key=lambda j: abs(lignes[j] - lignes[orpheline]),
            )
            for cible in voisines:
                remplace = {orpheline: cible}
                # The nearest neighbor may lie on the other side of the moved
                # edge: testing equality is not enough, strict order is needed,
                # otherwise the room comes out with its edges reversed.
                ecrase = any(
                    remplace.get(basse, basse) >= remplace.get(haute, haute)
                    for basse, haute in bords
                )
                if not ecrase:
                    fusion = (orpheline, cible)
                    break
            if fusion is not None:
                break
        if fusion is None:
            return lignes, bords, protegees
        orpheline, cible = fusion
        bords = [
            (cible if basse == orpheline else basse, cible if haute == orpheline else haute)
            for basse, haute in bords
        ]
        # Reindex, removing the absorbed line, protected ones included.
        garde = [k for k in range(len(lignes)) if k != orpheline]
        nouveau = {ancien: rang for rang, ancien in enumerate(garde)}
        lignes = [lignes[k] for k in garde]
        bords = [(nouveau[basse], nouveau[haute]) for basse, haute in bords]
        protegees = {nouveau[k] for k in protegees if k in nouveau}


def _couverture(
    incidences: list[tuple[str, int, int, int, int]], forme: tuple[int, int]
) -> np.ndarray:
    """Number of rooms covering each cell."""
    grille = np.zeros(forme, dtype=int)
    for _, gauche, droite, bas, haut in incidences:
        grille[gauche:droite, bas:haut] += 1
    return grille


def _retouches(
    incidence: tuple[str, int, int, int, int], forme: tuple[int, int]
) -> list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]]:
    """Growths and shrinks of one step, with the cells concerned.

    The boolean says whether it is an extension (true) or a reduction (false).
    Moving a single index by one step leaves the room rectangular by construction.
    """
    nom, gauche, droite, bas, haut = incidence
    largeur, hauteur = forme
    propositions: list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]] = []
    if gauche > 0:
        propositions.append(
            (
                (nom, gauche - 1, droite, bas, haut),
                (slice(gauche - 1, gauche), slice(bas, haut)),
                True,
            )
        )
    if droite < largeur:
        propositions.append(
            (
                (nom, gauche, droite + 1, bas, haut),
                (slice(droite, droite + 1), slice(bas, haut)),
                True,
            )
        )
    if bas > 0:
        propositions.append(
            (
                (nom, gauche, droite, bas - 1, haut),
                (slice(gauche, droite), slice(bas - 1, bas)),
                True,
            )
        )
    if haut < hauteur:
        propositions.append(
            (
                (nom, gauche, droite, bas, haut + 1),
                (slice(gauche, droite), slice(haut, haut + 1)),
                True,
            )
        )
    if droite - gauche > 1:
        propositions.append(
            (
                (nom, gauche + 1, droite, bas, haut),
                (slice(gauche, gauche + 1), slice(bas, haut)),
                False,
            )
        )
        propositions.append(
            (
                (nom, gauche, droite - 1, bas, haut),
                (slice(droite - 1, droite), slice(bas, haut)),
                False,
            )
        )
    if haut - bas > 1:
        propositions.append(
            (
                (nom, gauche, droite, bas + 1, haut),
                (slice(gauche, droite), slice(bas, bas + 1)),
                False,
            )
        )
        propositions.append(
            (
                (nom, gauche, droite, bas, haut - 1),
                (slice(gauche, droite), slice(haut - 1, haut)),
                False,
            )
        )
    return propositions


def _reparer_partition(
    incidences: list[tuple[str, int, int, int, int]],
    dedans: np.ndarray,
    budget: int,
) -> list[tuple[str, int, int, int, int]] | None:
    """Fix a partition that is off by a few cells, in indices only.

    After consolidation, **local** defects remain: a cell that is not
    covered, or covered twice. Measured on MSD, this is the dominant case:
    127 gaps and 115 overlaps of exactly one cell out of 1,200 corruptions.

    They are absorbed by growing or shrinking a room **by one step**, which
    leaves it rectangular by construction: only the indices move, never
    a coordinate. An extension is kept only if **all** the cells
    it gains are missing; a reduction, only if all those it
    frees are in excess. No structure is thus invented: a room gets back
    what a fault had taken from it, or loses what it had taken.

    Parameters
    ----------
    incidences : list of (str, int, int, int, int)
        Current incidences, possibly faulty.
    dedans : numpy.ndarray of bool
        Mask of the cells inside the outline.
    budget : int
        Maximum number of adjustments. Bounding it distinguishes a **repair** from a
        reconstruction: beyond it, the fault is no longer a wrong dimension but an
        order inconsistency, and one must refuse rather than guess.

    Returns
    -------
    list or None
        Repaired incidences, or ``None`` if the budget is exhausted before a partition.
    """
    forme = (int(dedans.shape[0]), int(dedans.shape[1]))
    incidences = list(incidences)
    for _ in range(budget):
        grille = _couverture(incidences, forme)
        manquantes = dedans & (grille < 1)
        excedents = (dedans & (grille > 1)) | (~dedans & (grille > 0))
        if not manquantes.any() and not excedents.any():
            return incidences
        meilleure: tuple[int, tuple[str, int, int, int, int], int] | None = None
        for rang, incidence in enumerate(incidences):
            for propose, cellules, extension in _retouches(incidence, forme):
                vise = manquantes if extension else excedents
                zone = vise[cellules]
                if zone.size and bool(zone.all()):
                    gain = int(zone.size)
                    if meilleure is None or gain > meilleure[2]:
                        meilleure = (rang, propose, gain)
        if meilleure is None:
            return None
        rang, propose, _ = meilleure
        incidences[rang] = propose
    grille = _couverture(incidences, forme)
    reste = bool((dedans & (grille != 1)).any() or (~dedans & (grille > 0)).any())
    return None if reste else incidences
