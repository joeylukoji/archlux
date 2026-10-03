"""Acquisition strategies: active vs random."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes
from archlux.errors import InvariantViolation

__all__ = ["AcquisitionStrategy", "RandomStrategy", "UncertaintyTimesDensity"]


class AcquisitionStrategy(Protocol):
    """Choose ``n`` indices among scored candidates."""

    def select(
        self,
        uncertainties: np.ndarray,
        densities: np.ndarray,
        *,
        n: int,
        seed: int,
        excluded: np.ndarray | None = None,
    ) -> np.ndarray:
        """Return ``n`` distinct indices in ``[0, N)``."""
        ...


def _validate(
    uncertainties: np.ndarray, densities: np.ndarray, *, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """Check the sizes and bounds of the selection inputs; return the raveled vectors."""
    inc = np.asarray(uncertainties, dtype=float).ravel()
    dens = np.asarray(densities, dtype=float).ravel()
    if inc.size != dens.size or inc.size == 0:
        raise InvariantViolation(("incertitudes and densites have incompatible lengths",))
    if n < 1:
        raise InvariantViolation(("selection n must be >= 1",))
    if n > inc.size:
        raise InvariantViolation((f"n={n} > number of candidates {inc.size}",))
    return inc, dens


def _available_mask(n_candidates: int, excluded: np.ndarray | None) -> np.ndarray:
    """Boolean mask of the free indices; reject ``excluded`` entries outside ``[0, N)``."""
    mask = np.ones(n_candidates, dtype=bool)
    if excluded is None:
        return mask
    excluded_i = np.asarray(excluded, dtype=int).ravel()
    if excluded_i.size == 0:
        return mask
    if np.any(excluded_i < 0) or np.any(excluded_i >= n_candidates):
        raise InvariantViolation(("excluded indices out of bounds",))
    mask[excluded_i] = False
    return mask


@renamed_attributes({"selectionner": "select"})
class UncertaintyTimesDensity:
    """``priority = uncertainty x density``. A product, not a sum."""

    def select(
        self,
        uncertainties: np.ndarray,
        densities: np.ndarray,
        *,
        n: int,
        seed: int,
        excluded: np.ndarray | None = None,
    ) -> np.ndarray:
        """Take the ``n`` highest scores, skipping ``excluded``."""
        del seed  # deterministic once the scores are fixed
        inc, dens = _validate(uncertainties, densities, n=n)
        scores = inc * dens
        available = np.flatnonzero(_available_mask(inc.size, excluded))
        if available.size < n:
            raise InvariantViolation((f"too few free candidates ({available.size}) for n={n}",))
        order = available[np.argsort(-scores[available], kind="stable")]
        return np.asarray(order[:n], dtype=int)


@renamed_attributes({"selectionner": "select"})
class RandomStrategy:
    """Uniform draw among the free candidates -- baseline at equal budget."""

    def select(
        self,
        uncertainties: np.ndarray,
        densities: np.ndarray,
        *,
        n: int,
        seed: int,
        excluded: np.ndarray | None = None,
    ) -> np.ndarray:
        """Sample ``n`` indices with the given seed."""
        inc, _dens = _validate(uncertainties, densities, n=n)
        available = np.flatnonzero(_available_mask(inc.size, excluded))
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
