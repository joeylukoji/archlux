"""archlux — corriger un plan généré vers la validité géométrique.

Interface publique **uniquement**. Ce fichier est délibérément court : tout ce qui n'y
figure pas est interne et peut changer sans préavis.

Deux garanties, de natures différentes, jamais confondues :

===============  =============  ==============================
Garantie         Nature         Vérification
===============  =============  ==============================
Géométrique      **exacte**     inspection finie, ``O(n²)``
Performance      probabiliste   prédiction conforme, ≥ 1 − α
===============  =============  ==============================

Examples
--------
>>> import archlux as ax
>>> plan = ax.Plan.from_json("propose.json")     # doctest: +SKIP
>>> q = ax.legalize(plan, ctx)                   # doctest: +SKIP
>>> q.certificat.geometrie.valide                # doctest: +SKIP
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from archlux._deprecation import Alias, lazy_aliases
from archlux._version import __version__
from archlux.errors import (
    DEPRECATED_NAMES as _DEPRECATED_EXCEPTIONS,
)
from archlux.errors import (
    ArchluxError,
    CalibrationLocked,
    GapNeedsTiling,
    GridNotRecoverable,
    InconsistentOrder,
    Infeasible,
    InvalidInput,
    InvalidSurrogate,
    InvariantViolation,
    MissingSeparation,
    ModelModified,
    UnsupportedInput,
)
from archlux.types import (
    BornePerformance,
    Certificat,
    Contexte,
    Mur,
    Orientation,
    Ouverture,
    Piece,
    Plan,
    PreuveGeometrique,
    Referentiel,
    Structure,
)

# Groupé par rôle et non trié alphabétiquement : la structure de cette liste *est* la
# carte de l'API publique. Un tri alphabétique mêlerait exceptions et modèle de données.
# ``light`` / ``bench`` / ``feasibility`` : chargés en paresseux via ``__getattr__`` pour
# que ``import archlux`` ne tire ni ``torch`` ni le banc.
__all__ = [  # noqa: RUF022
    # fonction publique — une seule, c'est la thèse du projet dans l'API
    "legalize",
    # modèle de données ; les entrées/sorties passent par Plan.from_json / Plan.to_json
    # et non par des fonctions libres : une seule façon de charger un plan.
    "Plan",
    "Piece",
    "Mur",
    "Ouverture",
    "Contexte",
    "Structure",
    "Orientation",
    "Referentiel",
    "Certificat",
    "PreuveGeometrique",
    "BornePerformance",
    # exceptions
    "ArchluxError",
    "InconsistentOrder",
    "MissingSeparation",
    "Infeasible",
    "InvalidInput",
    "UnsupportedInput",
    "GridNotRecoverable",
    "GapNeedsTiling",
    "InvariantViolation",
    "CalibrationLocked",
    "ModelModified",
    "InvalidSurrogate",
    # paquets publics (lazy)
    "light",
    "bench",
    "feasibility",
    "__version__",
]

_LAZY = frozenset({"light", "bench", "feasibility"})

if TYPE_CHECKING:
    # For mypy and IDEs only: the runtime resolves these on first use (``__getattr__``).
    # Without them ``ax.light.Daylight`` was invisible to type checkers (PLAN.md 3.8).
    # ``bench`` is not listed: no module may import it (ARCHITECTURE.md §5), so it stays
    # dynamic (``Any``) for type checkers.
    import archlux.feasibility as feasibility
    import archlux.light as light
    from archlux.api import legalize as legalize

# ``legalize`` drags in numpy, scipy.sparse, shapely and ortools (about 1 s): it is
# resolved on first use, so that ``import archlux`` stays under 0.5 s (PLAN.md 3.13).
_LAZY_FUNCTIONS = {"legalize": "archlux.api"}


def _lazy_attribute(name: str) -> Any:  # noqa: ANN401 - a lazy module or function
    """Charger ``light``, ``bench``, ``feasibility`` et ``legalize`` à la première utilisation."""
    # Import local : ne pas polluer ``dir(archlux)`` avec ``importlib``.
    import importlib

    if name in _LAZY:
        return importlib.import_module(f"archlux.{name}")
    if name in _LAZY_FUNCTIONS:
        function = getattr(importlib.import_module(_LAZY_FUNCTIONS[name]), name)
        globals()[name] = function  # resolved once: later lookups skip __getattr__
        return function
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# The former French exception names (ADR 0001): deprecated aliases until 1.0.0, then the
# lazy attributes above for everything else, so a from-import warns only once.
__getattr__ = lazy_aliases(
    __name__,
    {old: Alias(globals()[new], f"archlux.{new}") for old, new in _DEPRECATED_EXCEPTIONS.items()},
    fallback=_lazy_attribute,
)


def __dir__() -> list[str]:
    """Exposer uniquement l'API publique gelée (y compris les paquets lazy)."""
    return list(__all__)


# Note : ``light.appris``, ``solve`` et ``uq`` ne sont PAS importés ici.
# ``import archlux`` ne doit charger ni ``torch`` ni un modèle : c'est vérifié par
# ``tests/test_dependances.py`` et bloquant en CI.
