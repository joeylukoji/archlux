"""Acquisition strategies: active vs random."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation

__all__ = ["AcquisitionStrategy", "RandomStrategy", "UncertaintyTimesDensity"]


class AcquisitionStrategy(Protocol):
    """Choose ``n`` indices among scored candidates."""

    def selectionner(
        self,
        incertitudes: np.ndarray,
        densites: np.ndarray,
        *,
        n: int,
        seed: int,
        exclus: np.ndarray | None = None,
    ) -> np.ndarray:
        """Return ``n`` distinct indices in ``[0, N)``."""
        ...


def _valider(
    incertitudes: np.ndarray, densites: np.ndarray, *, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """Check the sizes and bounds of the selection inputs; return the raveled vectors."""
    inc = np.asarray(incertitudes, dtype=float).ravel()
    dens = np.asarray(densites, dtype=float).ravel()
    if inc.size != dens.size or inc.size == 0:
        raise InvariantViolation(("incertitudes and densites have incompatible lengths",))
    if n < 1:
        raise InvariantViolation(("selection n must be >= 1",))
    if n > inc.size:
        raise InvariantViolation((f"n={n} > number of candidates {inc.size}",))
    return inc, dens


def _masque_disponibles(n_candidats: int, exclus: np.ndarray | None) -> np.ndarray:
    """Boolean mask of the free indices; reject ``exclus`` entries outside ``[0, N)``."""
    masque = np.ones(n_candidats, dtype=bool)
    if exclus is None:
        return masque
    exclus_i = np.asarray(exclus, dtype=int).ravel()
    if exclus_i.size == 0:
        return masque
    if np.any(exclus_i < 0) or np.any(exclus_i >= n_candidats):
        raise InvariantViolation(("excluded indices out of bounds",))
    masque[exclus_i] = False
    return masque


class UncertaintyTimesDensity:
    """``priority = uncertainty x density``. A product, not a sum."""

    def selectionner(
        self,
        incertitudes: np.ndarray,
        densites: np.ndarray,
        *,
        n: int,
        seed: int,
        exclus: np.ndarray | None = None,
    ) -> np.ndarray:
        """Take the ``n`` highest scores, skipping ``exclus``."""
        del seed  # deterministic once the scores are fixed
        inc, dens = _valider(incertitudes, densites, n=n)
        scores = inc * dens
        disponibles = np.flatnonzero(_masque_disponibles(inc.size, exclus))
        if disponibles.size < n:
            raise InvariantViolation((f"too few free candidates ({disponibles.size}) for n={n}",))
        ordre = disponibles[np.argsort(-scores[disponibles], kind="stable")]
        return np.asarray(ordre[:n], dtype=int)


class RandomStrategy:
    """Uniform draw among the free candidates -- baseline at equal budget."""

    def selectionner(
        self,
        incertitudes: np.ndarray,
        densites: np.ndarray,
        *,
        n: int,
        seed: int,
        exclus: np.ndarray | None = None,
    ) -> np.ndarray:
        """Sample ``n`` indices with the given seed."""
        inc, _dens = _valider(incertitudes, densites, n=n)
        disponibles = np.flatnonzero(_masque_disponibles(inc.size, exclus))
        if disponibles.size < n:
            raise InvariantViolation((f"too few free candidates ({disponibles.size}) for n={n}",))
        rng = np.random.default_rng(seed)
        choix = rng.choice(disponibles, size=n, replace=False)
        return np.asarray(np.sort(choix), dtype=int)


__getattr__ = lazy_aliases(
    __name__,
    {
        "Aleatoire": Alias(RandomStrategy, "archlux.active.selection.RandomStrategy"),
        "StrategieAcquisition": Alias(
            AcquisitionStrategy, "archlux.active.selection.AcquisitionStrategy"
        ),
    },
)
