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


def _validate(
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


def _available_mask(n_candidates: int, exclus: np.ndarray | None) -> np.ndarray:
    """Boolean mask of the free indices; reject ``exclus`` entries outside ``[0, N)``."""
    mask = np.ones(n_candidates, dtype=bool)
    if exclus is None:
        return mask
    excluded_i = np.asarray(exclus, dtype=int).ravel()
    if excluded_i.size == 0:
        return mask
    if np.any(excluded_i < 0) or np.any(excluded_i >= n_candidates):
        raise InvariantViolation(("excluded indices out of bounds",))
    mask[excluded_i] = False
    return mask


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
        inc, dens = _validate(incertitudes, densites, n=n)
        scores = inc * dens
        available = np.flatnonzero(_available_mask(inc.size, exclus))
        if available.size < n:
            raise InvariantViolation((f"too few free candidates ({available.size}) for n={n}",))
        ordre = available[np.argsort(-scores[available], kind="stable")]
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
        inc, _dens = _validate(incertitudes, densites, n=n)
        available = np.flatnonzero(_available_mask(inc.size, exclus))
        if available.size < n:
            raise InvariantViolation((f"too few free candidates ({available.size}) for n={n}",))
        rng = np.random.default_rng(seed)
        choice = rng.choice(available, size=n, replace=False)
        return np.asarray(np.sort(choice), dtype=int)


__getattr__ = lazy_aliases(
    __name__,
    {
        "Aleatoire": Alias(RandomStrategy, "archlux.active.selection.RandomStrategy"),
        "StrategieAcquisition": Alias(
            AcquisitionStrategy, "archlux.active.selection.AcquisitionStrategy"
        ),
    },
)
