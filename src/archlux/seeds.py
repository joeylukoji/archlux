"""Named sub-seeds derived from one run seed (PLAN.md phase 2, AUDIT.md Q-M5).

Two components that draw from ``seed`` and ``seed + 1`` share a random stream across
runs: the campaign of seed 17 at cycle 1 replays the campaign of seed 18 at cycle 0.
A named derivation gives every component its own stream, and the same name always gives
the same stream, on every machine and version.

The hash is **cryptographic and unsalted** (BLAKE2b truncated to 32 bits): Python's
``hash()`` is randomized per process, which would make the derivation irreproducible.

This module imports only ``hashlib``, so every layer may depend on it; ``bench.graines``
and ``data.synthese`` use it too.
"""

from __future__ import annotations

import hashlib

__all__ = ["derive"]

_BYTES = 4
"""Width of a sub-seed: 32 bits, the range ``numpy.random`` accepts."""


def derive(seed: int, name: str) -> int:
    """Derive a stable sub-seed from a run seed and a stream name.

    Parameters
    ----------
    seed : int
        Root seed of the run, as recorded in its manifest.
    name : str
        Stream name (``"selection/3"``, ``"calibration"``...). Two names give two
        independent streams; one name always gives the same stream.

    Returns
    -------
    int
        Sub-seed in ``[0, 2**32)``.

    Examples
    --------
    >>> derive(17, "selection/1") == derive(18, "selection/0")
    False
    >>> derive(17, "calibration") == derive(17, "calibration")
    True
    """
    digest = hashlib.blake2b(f"{seed}:{name}".encode(), digest_size=_BYTES).digest()
    return int.from_bytes(digest, "big")
