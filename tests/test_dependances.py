"""Les règles de dépendance de `ARCHITECTURE.md` §5 sont exécutables, pas déclaratives.

Ce fichier est écrit **avant** toute implémentation, et non après. Une violation de
couche découverte au jalon 4 coûte un refactor ; découverte au premier commit, elle coûte
une minute. La CI l'exécute dans une étape dédiée et bloquante.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1] / "src" / "archlux"

# Ce que chaque paquet a le droit d'importer, à l'intérieur d'archlux.
# `solve` dépend de `light.protocol` SEULEMENT, jamais d'une implémentation.
AUTORISE: dict[str, frozenset[str]] = {
    # `feasibility`, `light`: imported under TYPE_CHECKING only, so that type checkers see
    # the lazy packages (PLAN.md 3.8). `test_import_cost` proves that `import archlux`
    # loads none of them. `bench` cannot be listed: nobody imports it.
    "__init__": frozenset({"types", "errors", "api", "io", "feasibility", "light"}),
    # `types` peut joindre `errors` : les deux sont des racines du graphe, `errors` ne
    # dépend de rien et n'importe surtout pas `types`. L'arête ne crée aucun cycle et
    # évite que chaque type doive lever `Exception` nue faute d'exception typée sous la
    # main (`ARCHITECTURE.md` §7).
    "types": frozenset({"errors"}),
    "errors": frozenset(),
    # Deprecated module name (PLAN.md 3.9): a shim that forwards to `errors`.
    "erreurs": frozenset({"errors"}),
    # Leaves importable by every layer; they import nothing (see LEAVES below).
    "_version": frozenset(),
    "tolerances": frozenset(),
    "seeds": frozenset(),
    "arrays": frozenset(),
    "_deprecation": frozenset(),
    # Door validation of the public arguments (PLAN.md 3.1): a leaf over `types`.
    "validation": frozenset({"types", "errors"}),
    "geom": frozenset({"types", "errors"}),
    "lmo": frozenset({"types", "errors", "geom"}),
    "solve": frozenset({"types", "errors", "geom", "lmo", "light.protocol"}),
    "light": frozenset({"types", "errors", "orient"}),
    "orient": frozenset({"types", "errors"}),
    "uq": frozenset({"types", "errors"}),
    # `data.loaders` convertit un corpus reel (WKT) en `Plan` : il redresse via
    # `orient.circular.direction_dominante` et decoupe via `geom.rectilinear`.
    # Aretes ajoutees a `ARCHITECTURE.md` §5 : `geom` et `orient` sont purs et
    # n'importent pas `data`, donc aucun cycle. `data` ne touche ni `lmo`, ni
    # `solve`, ni `light` : il produit des entrees, il ne resout rien.
    "data": frozenset({"types", "errors", "uq", "orient", "geom"}),
    "certify": frozenset({"types", "errors", "geom", "uq"}),
    "io": frozenset({"types", "errors"}),
    # Apprentissage actif : orchestrateur feuille — protocole light + uq, pas torch.
    "active": frozenset({"types", "errors", "light.protocol", "uq"}),
    # Export BIM : feuille — types + erreurs ; ifcopenshell optionnel (hors archlux).
    "export": frozenset({"types", "errors"}),
    # Faisabilité : facade sur legalize / Farkas — exacte, sans lumière.
    "feasibility": frozenset({"types", "errors", "api"}),
    "bench": frozenset(
        {
            "types",
            "errors",
            "geom",
            "lmo",
            "solve",
            "light",
            "orient",
            "uq",
            "certify",
            "io",
            "data",
            "active",
            "export",
        }
    ),
    "api": frozenset(
        {
            "types",
            "errors",
            "validation",
            "geom",
            "lmo",
            "solve",
            "light.protocol",
            "certify",
            "io",
        }
    ),
}

LEAVES: dict[str, frozenset[str]] = {
    "_version": frozenset(),
    "tolerances": frozenset({"__future__", "typing"}),
    "seeds": frozenset({"__future__", "hashlib"}),
    "arrays": frozenset({"__future__", "typing", "numpy", "warnings"}),
    "_deprecation": frozenset(
        {
            "__future__",
            "functools",
            "importlib",
            "sys",
            "warnings",
            "dataclasses",
            "typing",
            "collections",
        }
    ),
}
"""Modules importable by every layer, with the only imports they may make themselves."""

# torch n'est tolérable que dans light.learned, et en import paresseux.
TORCH_TOLERE = frozenset({"light.learned"})

# Dérogations nominatives, chacune adossée à une décision écrite (ADR-5 du blueprint).
# `Plan.from_json` et `Certificate.report()` sont l'API publique fixée par
# `DOCUMENTATION.md` §3 et §5. Les honorer demande à `types` de déléguer vers `io` et
# `certify` — par import **local**, à l'appel, donc sans cycle à l'import.
# La dérogation est nominative et non un assouplissement de la règle : tout autre import
# depuis `types` échoue toujours.
EXEMPTIONS: dict[str, frozenset[str]] = {
    # ADR-9: the export facades `Plan.to_dxf`, `to_ifc`, `to_svg` (PLAN.md 3.11).
    "types": frozenset({"archlux.io.json_io", "archlux.certify.report", "archlux.export"}),
}


def _modules() -> list[Path]:
    """Tous les modules, ``__init__.py`` **compris**.

    Les exclure laisserait un trou béant : un paquet peut violer une couche depuis son
    ``__init__``, et c'est même l'endroit le plus probable.
    """
    return sorted(RACINE.rglob("*.py"))


def _paquet(fichier: Path) -> str:
    rel = fichier.relative_to(RACINE)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def _chemin_module(fichier: Path) -> str:
    rel = fichier.relative_to(RACINE).with_suffix("")
    return ".".join(rel.parts)


def _imports(fichier: Path) -> set[str]:
    """Imports absolus de ``archlux.*`` et de ``torch``, y compris sous TYPE_CHECKING."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    trouves: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
            trouves.add(noeud.module)
    return trouves


@pytest.mark.parametrize("fichier", _modules(), ids=_chemin_module)
def test_les_couches_respectent_les_dependances(fichier: Path) -> None:
    """Aucun module n'importe une couche que `ARCHITECTURE.md` §5 lui interdit."""
    paquet = _paquet(fichier)
    autorise = AUTORISE[paquet]
    exemptions = EXEMPTIONS.get(paquet, frozenset())
    for cible in sorted(_imports(fichier)):
        if cible == "archlux":
            # `from archlux import X` runs `archlux/__init__.py`, which loads `api` and
            # the whole legalization chain. No internal module may do that: the version
            # comes from `archlux._version`.
            raise AssertionError(
                f"{_chemin_module(fichier)} imports the root package `archlux`: "
                "forbidden inside the library (import the precise module instead)."
            )
        if not cible.startswith("archlux.") or cible in exemptions:
            continue
        reste = cible.removeprefix("archlux.")
        if reste in LEAVES:
            continue  # dependency-free leaves, importable by every layer
        paquet_cible = reste.split(".")[0]
        if paquet_cible == paquet:
            continue  # import interne au paquet
        ok = paquet_cible in autorise or any(
            reste == permis or reste.startswith(permis + ".") for permis in autorise
        )
        assert ok, (
            f"{_chemin_module(fichier)} importe {cible} : interdit. "
            f"Couches autorisées pour '{paquet}' : {sorted(autorise)}."
        )


@pytest.mark.parametrize("fichier", _modules(), ids=_chemin_module)
def test_le_noyau_ne_reference_pas_torch(fichier: Path) -> None:
    """Seul ``light.learned`` peut nommer ``torch``."""
    module = _chemin_module(fichier)
    reference = any(c == "torch" or c.startswith("torch.") for c in _imports(fichier))
    assert not reference or module in TORCH_TOLERE, f"{module} référence torch"


def test_lmo_n_importe_jamais_light() -> None:
    """L'oracle ignore d'où vient ``c`` — c'est le cœur de l'architecture."""
    for fichier in _modules():
        if _paquet(fichier) != "lmo":
            continue
        assert not any(c.startswith("archlux.light") for c in _imports(fichier)), (
            f"{_chemin_module(fichier)} importe light"
        )


def test_solve_ne_depend_que_du_protocole_light() -> None:
    """``solve`` ne connaît aucune implémentation concrète de substitut."""
    for fichier in _modules():
        if _paquet(fichier) != "solve":
            continue
        for cible in _imports(fichier):
            if cible.startswith("archlux.light"):
                assert cible == "archlux.light.protocol", (
                    f"{_chemin_module(fichier)} importe {cible} ; "
                    "seul archlux.light.protocol est autorisé"
                )


def test_personne_n_importe_bench() -> None:
    """``bench`` est une feuille de l'arbre de dépendances."""
    for fichier in _modules():
        if _paquet(fichier) == "bench":
            continue
        assert not any(c.startswith("archlux.bench") for c in _imports(fichier)), (
            f"{_chemin_module(fichier)} importe bench"
        )


def test_le_noyau_n_importe_pas_torch() -> None:
    """``import archlux`` ne doit charger ``torch`` dans aucun cas (`ARCHITECTURE.md` §5)."""
    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_les_exemptions_restent_rares_et_nommees() -> None:
    """Une dérogation non listée ici n'existe pas ; la liste doit rester courte.

    Ce test n'a l'air de rien : il empêche la liste d'exemptions de devenir le trou par
    lequel la règle de couches se vide, une entrée à la fois.
    """
    total = sum(len(v) for v in EXEMPTIONS.values())
    assert total <= 3, "toute nouvelle dérogation exige une ADR dans le blueprint"


@pytest.mark.parametrize("leaf", sorted(LEAVES))
def test_leaves_import_nothing_else(leaf: str) -> None:
    """A leaf may be imported by every layer only because it depends on nothing."""
    arbre = ast.parse((RACINE / f"{leaf}.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            imported.add((noeud.module or "").split(".")[0])
    assert imported <= LEAVES[leaf], f"{leaf} imports {sorted(imported - LEAVES[leaf])}"


@pytest.mark.parametrize("fichier", _modules(), ids=_chemin_module)
def test_no_relative_imports(fichier: Path) -> None:
    """Relative imports escape the layer check above, which only reads absolute ones."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    relative = [n.lineno for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.level]
    assert not relative, f"{_chemin_module(fichier)}: relative imports at lines {relative}"


_ROOT_EAGER = frozenset({"types", "errors"})
"""``archlux/__init__.py``'s own eager top-level imports: initializing the parent
package is unavoidable before any ``import archlux.<x>`` runs, so every dynamic check
below sees these two regardless of ``x`` (`test_import_cost.py` checks the root itself
does not go further than this)."""


def _closure(paquet: str) -> frozenset[str]:
    """Every top-level layer ``paquet`` may reach, directly or through one it may reach.

    ``AUTORISE`` entries name the layers a package may import from; this expands that
    one level to every level, so a name reached only *through* an allowed layer (e.g.
    ``api`` reaches ``uq`` through ``certify``) is not mistaken for a violation.
    """
    seen: set[str] = {paquet, *_ROOT_EAGER}
    pile = [paquet, *_ROOT_EAGER]
    while pile:
        for cible in AUTORISE.get(pile.pop(), frozenset()):
            racine = cible.split(".")[0]
            if racine not in seen:
                seen.add(racine)
                pile.append(racine)
    return frozenset(seen)


_FRESH_IMPORT = """\
import importlib, pkgutil, sys
package = importlib.import_module("archlux." + sys.argv[1])
# A lazy facade loads almost nothing on `import`: also load every submodule and resolve
# every public name, so the check sees what the package can actually pull in.
for info in pkgutil.walk_packages(getattr(package, "__path__", []), package.__name__ + "."):
    # torch-only, optional (TORCH_TOLERE); `appris` is its deprecated module name (ADR 0001)
    if info.name not in {"archlux.light.learned", "archlux.light.appris"}:
        importlib.import_module(info.name)
for name in getattr(package, "__all__", []):
    getattr(package, name)
print(",".join(sorted(m for m in sys.modules if m.startswith("archlux.") or m == "torch")))
"""


def _fresh_import(paquet: str) -> frozenset[str]:
    """Modules (``archlux.*`` and ``torch``) loaded by a fresh, exhaustive import."""
    result = subprocess.run(
        [sys.executable, "-c", _FRESH_IMPORT, paquet], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return frozenset(m for m in result.stdout.strip().split(",") if m)


_LIGHT_IMPLEMENTATIONS = ("archlux.light.",)
"""Every ``light`` submodule; ``archlux.light.protocol`` is the one allowed exception."""

FORBIDDEN: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    # importer: (forbidden module prefixes, modules exempted from them) — ARCHITECTURE.md
    # §5 "FORBIDDEN", checked WITHOUT any transitive closure: what loads is what counts.
    "geom": (("torch",), frozenset()),
    "lmo": (("torch", "archlux.light"), frozenset()),
    "solve": (("torch", *_LIGHT_IMPLEMENTATIONS), frozenset({"archlux.light.protocol"})),
    "certify": (("torch",), frozenset()),
    "light": (("archlux.geom", "archlux.lmo", "archlux.solve"), frozenset()),
    "active": (_LIGHT_IMPLEMENTATIONS, frozenset({"archlux.light.protocol"})),
    "export": (("archlux.geom", "archlux.certify"), frozenset()),
    "data": (("archlux.lmo", "archlux.solve", "archlux.light"), frozenset()),
    # Justified exception (ARCHITECTURE.md §5): `is_feasible` calls `legalize`, so
    # `feasibility` depends on `api` by design and reaches `light.protocol` and `uq`
    # through it (api -> solve -> light.protocol, api -> certify -> uq). It never imports
    # them directly (the static AUTORISE walk forbids that) and loads no light
    # implementation; `test_feasibility_reaches_light_and_uq_only_through_api` proves it
    # loads nothing `api` does not load already.
    "feasibility": (_LIGHT_IMPLEMENTATIONS, frozenset({"archlux.light.protocol"})),
}
"""ARCHITECTURE.md §5 FORBIDDEN rules, by importer. "No module may import bench" and
"no torch outside ``light.learned``" apply to every package and are checked separately."""


def _hits(module: str, prefix: str) -> bool:
    """``"archlux.light"`` matches the package and its submodules; ``"archlux.light."``
    only the submodules (the lazy facade itself loads no implementation)."""
    if prefix.endswith("."):
        return module.startswith(prefix)
    return module == prefix or module.startswith(prefix + ".")


@pytest.mark.parametrize("paquet", sorted(FORBIDDEN))
def test_a_fresh_import_breaks_no_forbidden_rule(paquet: str) -> None:
    """Each §5 FORBIDDEN rule, against ``sys.modules`` after a fresh exhaustive import."""
    prefixes, allowed = FORBIDDEN[paquet]
    broken = sorted(
        m for m in _fresh_import(paquet) if m not in allowed and any(_hits(m, p) for p in prefixes)
    )
    assert not broken, f"import archlux.{paquet} loads forbidden {broken} (ARCHITECTURE.md §5)"


@pytest.mark.parametrize("paquet", sorted(p for p in AUTORISE if p != "__init__"))
def test_a_fresh_import_loads_no_bench_and_no_torch(paquet: str) -> None:
    """No package but ``bench`` loads ``bench``; none loads ``torch`` (``learned`` aside)."""
    loaded = _fresh_import(paquet)
    assert "torch" not in loaded
    if paquet != "bench":
        assert not any(_hits(m, "archlux.bench") for m in loaded)


def test_feasibility_reaches_light_and_uq_only_through_api() -> None:
    """The §5 exception for ``feasibility`` is exactly "through ``api``", nothing more."""
    extra = _fresh_import("feasibility") - _fresh_import("api")
    assert all(_hits(m, "archlux.feasibility") for m in extra), sorted(extra)


@pytest.mark.parametrize("paquet", sorted(p for p in AUTORISE if p != "__init__"))
def test_a_fresh_import_loads_only_the_declared_layers(paquet: str) -> None:
    """The static AST walk above cannot see a dynamic ``importlib.import_module`` call,
    or a transitive import the declared sets did not anticipate (PLAN.md phase 4,
    block 1: a *dynamic*, ``sys.modules``-based check, alongside the static one).

    ``__init__`` (the root package) is excluded: its own laziness is already checked,
    more precisely, by ``test_import_cost.py``.
    """
    autorise = _closure(paquet)
    for module in sorted(_fresh_import(paquet) - {"torch"}):
        module = module.removeprefix("archlux.")
        racine = module.split(".")[0]
        if racine in LEAVES or racine in autorise:
            continue
        pytest.fail(
            f"import archlux.{paquet} actually loads archlux.{module}, not reachable "
            f"through AUTORISE[{paquet!r}] = {sorted(AUTORISE[paquet])}"
        )
