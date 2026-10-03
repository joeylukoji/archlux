"""Emission of the reproducibility manifest.

Every run produces one, without exception. A result without a manifest is not
reproducible, and a non-reproducible result is not a result.
"""

from __future__ import annotations

import datetime as dt
import sys
from importlib.metadata import PackageNotFoundError, version

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux._version import __version__
from archlux.types import Manifest, ModelTrace

__all__ = ["emit"]

_TRACKED_PACKAGES = ("numpy", "scipy", "networkx", "shapely", "ortools", "torch")
"""Packages whose version changes the numerical results, and thus the conclusions.

``torch`` appears here without being imported: only its version is recorded, and only
if it is already installed. Recording a version is not loading a library.
"""


def _installed_version(name: str) -> str | None:
    """Installed version of a package, or ``None`` if it is absent."""
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _environment() -> tuple[tuple[str, str], ...]:
    """Versions of Python and the present packages, sorted.

    An absent optional package is **omitted**, never noted as ``"absent"``: the
    manifest describes what was used, not what was missing.
    """
    snapshot = {"python": sys.version.split()[0]}
    for name in _TRACKED_PACKAGES:
        version = _installed_version(name)
        if version is not None:
            snapshot[name] = version
    return tuple(sorted(snapshot.items()))


@renamed_parameters(
    {
        "empreinte_donnees": "data_fingerprint",
        "decoupage": "split",
        "parametres": "parameters",
        "modele": "model",
    }
)
def emit(
    *,
    seed: int,
    data_fingerprint: str | None = None,
    split: str | None = None,
    parameters: dict[str, str] | None = None,
    model: ModelTrace | None = None,
) -> Manifest:
    """Build the manifest for the current run.

    Parameters
    ----------
    seed : int
        Root seed. **Mandatory, no default** (`ARCHITECTURE.md` §7): an implicit
        seed is a lost seed, and the run stops being replayable.
    data_fingerprint : str or None, optional
        ``sha256`` of the corpus used.
    split : str or None, optional
        Identifier of the frozen split, for example ``"splits/v2"``.
    parameters : dict of str to str or None, optional
        Run parameters. They are frozen into **sorted** pairs: without sorting, the
        manifest fingerprint would change from one run to another and would no
        longer identify anything.
    model : ModelTrace or None, optional
        Fingerprint of the weights and calibration size (mandatory for
        ``bench.run``).

    Returns
    -------
    Manifest
        Version, UTC timestamp, seed, fingerprints and environment versions.

    Guarantees
    ----------
    - No computation guarantee: this type is a **trace**. It does not say that a
      result is correct, only under what conditions it was produced.

    Complexity
    ----------
    O(k) over the number of tracked packages.
    """
    return Manifest(
        version=__version__,
        timestamp=dt.datetime.now(dt.UTC).isoformat(),
        seed=seed,
        data_fingerprint=data_fingerprint,
        split=split,
        environment=_environment(),
        parameters=tuple(sorted((parameters or {}).items())),
        model=model,
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "emettre": Alias(emit, "archlux.bench.manifest.emit"),
    },
)
