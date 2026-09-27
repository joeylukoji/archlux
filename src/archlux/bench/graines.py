"""Deterministic seed derivation. No implicit seed anywhere.

One seed per run, derived into named sub-seeds: two components never share a random
stream, and a run replays exactly.

The hash is **cryptographic and unsalted** (truncated BLAKE2b). This is deliberate:
Python's ``hash()`` is randomized from one process to another, which would make
derivation non-reproducible — exactly what this module exists to prevent.
"""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.seeds import derive as _derive

__all__ = ["derive"]


def derive(seed: int, name: str) -> int:
    """Derive a stable sub-seed from a root seed and a name.

    Parameters
    ----------
    seed : int
        Root seed of the run, as recorded in the manifest.
    name : str
        Stream name (``"calibration"``, ``"permutation"``, …). Two distinct names
        give two independent streams; the same name always gives back the same
        stream.

    Returns
    -------
    int
        Sub-seed in ``[0, 2**32)``, stable across versions and machines.

    Complexity
    ----------
    O(len(name)).

    Examples
    --------
    >>> from archlux.bench.graines import derive
    >>> derive(17, "calibration") == derive(17, "calibration")
    True
    >>> derive(17, "calibration") == derive(17, "permutation")
    False
    """
    return _derive(seed, name)


__getattr__ = lazy_aliases(
    __name__,
    {
        "deriver": Alias(derive, "archlux.bench.graines.derive"),
    },
)
