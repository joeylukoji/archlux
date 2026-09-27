"""Empirical density of the plans visited by the optimizer."""

from __future__ import annotations

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation

__all__ = ["kernel_density"]

_EPS = 1e-12


def kernel_density(
    candidats: np.ndarray, reference: np.ndarray, *, bande: float | None = None
) -> np.ndarray:
    """Isotropic Gaussian density estimated on the optimizer's outputs.

    Parameters
    ----------
    candidats : numpy.ndarray
        Shape ``(n, d)`` — candidate plans (vectorized).
    reference : numpy.ndarray
        Shape ``(m, d)`` — plans produced by the optimizer (useful domain).
    bande : float or None, optional
        Kernel bandwidth. Default: Scott's rule on the reference.

    Returns
    -------
    numpy.ndarray
        Densities ``(n,)``, positive. A candidate far from every optimizer
        output has a density ~0 → zero active priority.
    """
    cand = np.asarray(candidats, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if cand.ndim != 2 or ref.ndim != 2:
        raise InvariantViolation(("candidats and reference must be rank 2",))
    if cand.shape[1] != ref.shape[1]:
        raise InvariantViolation(("candidats / reference dimensions are incompatible",))
    if ref.shape[0] == 0 or cand.shape[0] == 0:
        raise InvariantViolation(("reference and candidats must both be non-empty",))
    d = cand.shape[1]
    if bande is None:
        # Scott: n^{-1/(d+4)} * mean standard deviation.
        sigma = float(np.mean(np.std(ref, axis=0)) + _EPS)
        bande = sigma * (ref.shape[0] ** (-1.0 / (d + 4)))
        bande = max(bande, _EPS)
    if bande <= 0.0:
        raise InvariantViolation(("bande must be > 0",))
    # density_i ∝ mean_j exp(-||c_i - r_j||² / (2 h²))
    # To avoid underflow: work with nearest-neighbor distance + local mean.
    diff = cand[:, None, :] - ref[None, :, :]
    dist2 = np.sum(diff * diff, axis=2)
    noyaux = np.exp(-0.5 * dist2 / (bande * bande))
    return np.asarray(np.maximum(np.mean(noyaux, axis=1), _EPS), dtype=float)


__getattr__ = lazy_aliases(
    __name__,
    {
        "densite_noyau": Alias(kernel_density, "archlux.active.densite.kernel_density"),
    },
)
