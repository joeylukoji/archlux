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

from types import ModuleType

from archlux._version import __version__
from archlux.api import legalize
from archlux.erreurs import (
    ArchluxError,
    CalibrationVerrouillee,
    Infaisable,
    InvariantViole,
    ModeleModifie,
    OrdreIncoherent,
    SeparationManquante,
    SubstitutInvalide,
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
    "OrdreIncoherent",
    "SeparationManquante",
    "Infaisable",
    "InvariantViole",
    "CalibrationVerrouillee",
    "ModeleModifie",
    "SubstitutInvalide",
    # paquets publics (lazy)
    "light",
    "bench",
    "feasibility",
    "__version__",
]

_LAZY = frozenset({"light", "bench", "feasibility"})


def __getattr__(name: str) -> ModuleType:
    """Charger ``light`` / ``bench`` / ``feasibility`` à la première attribution."""
    if name in _LAZY:
        # Import local : ne pas polluer ``dir(archlux)`` avec ``importlib``.
        import importlib

        return importlib.import_module(f"archlux.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Exposer uniquement l'API publique gelée (y compris les paquets lazy)."""
    return list(__all__)


# Note : ``light.appris``, ``solve`` et ``uq`` ne sont PAS importés ici.
# ``import archlux`` ne doit charger ni ``torch`` ni un modèle : c'est vérifié par
# ``tests/test_dependances.py`` et bloquant en CI.
