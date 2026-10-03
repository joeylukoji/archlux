"""The dependency rules of `ARCHITECTURE.md` §5 are executable, not declarative.

This file was written **before** any implementation, not after. A layer violation found
at milestone 4 costs a refactor; found at the first commit, it costs a minute. The CI
runs it in a dedicated, blocking step.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "archlux"

# What each package may import, inside archlux.
# `solve` depends on `light.protocol` ONLY, never on an implementation.
ALLOWED: dict[str, frozenset[str]] = {
    # `feasibility`, `light`: imported under TYPE_CHECKING only, so that type checkers see
    # the lazy packages (PLAN.md 3.8). `test_import_cost` proves that `import archlux`
    # loads none of them. `bench` cannot be listed: nobody imports it.
    "__init__": frozenset({"types", "errors", "api", "io", "feasibility", "light"}),
    # `types` may reach `errors`: both are roots of the graph, `errors` depends on
    # nothing and above all does not import `types`. The edge creates no cycle and saves
    # every type from raising a bare `Exception` for lack of a typed exception at hand
    # (`ARCHITECTURE.md` §7).
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
    # `data.loaders` converts a real corpus (WKT) into a `Plan`: it straightens it via
    # `orient.circular` and cuts it via `geom.rectilinear`. Edges added to
    # `ARCHITECTURE.md` §5: `geom` and `orient` are pure and do not import `data`, so
    # there is no cycle. `data` touches neither `lmo`, nor `solve`, nor `light`: it
    # produces inputs, it solves nothing.
    "data": frozenset({"types", "errors", "uq", "orient", "geom"}),
    "certify": frozenset({"types", "errors", "geom", "uq"}),
    "io": frozenset({"types", "errors"}),
    # Active learning: a leaf orchestrator; light protocol + uq, no torch.
    "active": frozenset({"types", "errors", "light.protocol", "uq"}),
    # BIM export: a leaf; types + errors; ifcopenshell optional (outside archlux).
    "export": frozenset({"types", "errors"}),
    # Feasibility: a facade over legalize / Farkas; exact, no light.
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

# torch is tolerated only in light.learned, and as a lazy import.
TORCH_TOLERATED = frozenset({"light.learned"})

# Named exemptions, each backed by a written decision (ADR-5 of the blueprint).
# `Plan.from_json` and `Certificate.report()` are the public API fixed by
# `DOCUMENTATION.md` §3 and §5. Honouring them requires `types` to delegate to `io` and
# `certify`, by a **local** import at call time, hence without an import cycle.
# The exemption is named, not a loosening of the rule: any other import from `types`
# still fails.
EXEMPTIONS: dict[str, frozenset[str]] = {
    # ADR-9: the export facades `Plan.to_dxf`, `to_ifc`, `to_svg` (PLAN.md 3.11).
    "types": frozenset({"archlux.io.json_io", "archlux.certify.report", "archlux.export"}),
}


def _modules() -> list[Path]:
    """Every module, ``__init__.py`` **included**.

    Excluding them would leave a gaping hole: a package can break a layer from its
    ``__init__``, and that is even the most likely place.
    """
    return sorted(SRC_ROOT.rglob("*.py"))


def _package(source_file: Path) -> str:
    rel = source_file.relative_to(SRC_ROOT)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def _module_path(source_file: Path) -> str:
    rel = source_file.relative_to(SRC_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _imports(source_file: Path) -> set[str]:
    """Absolute imports of ``archlux.*`` and ``torch``, TYPE_CHECKING included."""
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


@pytest.mark.parametrize("source_file", _modules(), ids=_module_path)
def test_layers_respect_the_dependencies(source_file: Path) -> None:
    """No module imports a layer that `ARCHITECTURE.md` §5 forbids it."""
    package = _package(source_file)
    allowed_layers = ALLOWED[package]
    exemptions = EXEMPTIONS.get(package, frozenset())
    for target in sorted(_imports(source_file)):
        if target == "archlux":
            # `from archlux import X` runs `archlux/__init__.py`, which loads `api` and
            # the whole legalization chain. No internal module may do that: the version
            # comes from `archlux._version`.
            raise AssertionError(
                f"{_module_path(source_file)} imports the root package `archlux`: "
                "forbidden inside the library (import the precise module instead)."
            )
        if not target.startswith("archlux.") or target in exemptions:
            continue
        rest = target.removeprefix("archlux.")
        if rest in LEAVES:
            continue  # dependency-free leaves, importable by every layer
        target_package = rest.split(".")[0]
        if target_package == package:
            continue  # import internal to the package
        ok = target_package in allowed_layers or any(
            rest == permitted or rest.startswith(permitted + ".") for permitted in allowed_layers
        )
        assert ok, (
            f"{_module_path(source_file)} imports {target}: forbidden. "
            f"Allowed layers for '{package}': {sorted(allowed_layers)}."
        )


@pytest.mark.parametrize("source_file", _modules(), ids=_module_path)
def test_the_core_does_not_reference_torch(source_file: Path) -> None:
    """Only ``light.learned`` may name ``torch``."""
    module = _module_path(source_file)
    references_torch = any(c == "torch" or c.startswith("torch.") for c in _imports(source_file))
    assert not references_torch or module in TORCH_TOLERATED, f"{module} references torch"


def test_lmo_never_imports_light() -> None:
    """The oracle does not know where ``c`` comes from: the heart of the architecture."""
    for source_file in _modules():
        if _package(source_file) != "lmo":
            continue
        assert not any(c.startswith("archlux.light") for c in _imports(source_file)), (
            f"{_module_path(source_file)} imports light"
        )


def test_solve_depends_only_on_the_light_protocol() -> None:
    """``solve`` knows no concrete surrogate implementation."""
    for source_file in _modules():
        if _package(source_file) != "solve":
            continue
        for target in _imports(source_file):
            if target.startswith("archlux.light"):
                assert target == "archlux.light.protocol", (
                    f"{_module_path(source_file)} imports {target}; "
                    "only archlux.light.protocol is allowed"
                )


def test_nobody_imports_bench() -> None:
    """``bench`` is a leaf of the dependency tree."""
    for source_file in _modules():
        if _package(source_file) == "bench":
            continue
        assert not any(c.startswith("archlux.bench") for c in _imports(source_file)), (
            f"{_module_path(source_file)} imports bench"
        )


def test_the_core_does_not_import_torch() -> None:
    """``import archlux`` must never load ``torch`` (`ARCHITECTURE.md` §5)."""
    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_exemptions_stay_rare_and_named() -> None:
    """An exemption not listed here does not exist; the list must stay short.

    This test looks like nothing: it keeps the exemption list from becoming the hole
    through which the layer rule drains, one entry at a time.
    """
    total = sum(len(v) for v in EXEMPTIONS.values())
    assert total <= 3, "any new exemption requires an ADR in the blueprint"


@pytest.mark.parametrize("leaf", sorted(LEAVES))
def test_leaves_import_nothing_else(leaf: str) -> None:
    """A leaf may be imported by every layer only because it depends on nothing."""
    tree = ast.parse((SRC_ROOT / f"{leaf}.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= LEAVES[leaf], f"{leaf} imports {sorted(imported - LEAVES[leaf])}"


@pytest.mark.parametrize("source_file", _modules(), ids=_module_path)
def test_no_relative_imports(source_file: Path) -> None:
    """Relative imports escape the layer check above, which only reads absolute ones."""
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    relative = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]
    assert not relative, f"{_module_path(source_file)}: relative imports at lines {relative}"


_ROOT_EAGER = frozenset({"types", "errors"})
"""``archlux/__init__.py``'s own eager top-level imports: initializing the parent
package is unavoidable before any ``import archlux.<x>`` runs, so every dynamic check
below sees these two regardless of ``x`` (`test_import_cost.py` checks the root itself
does not go further than this)."""


def _closure(package: str) -> frozenset[str]:
    """Every top-level layer ``package`` may reach, directly or through one it may reach.

    ``ALLOWED`` entries name the layers a package may import from; this expands that
    one level to every level, so a name reached only *through* an allowed layer (e.g.
    ``api`` reaches ``uq`` through ``certify``) is not mistaken for a violation.
    """
    seen: set[str] = {package, *_ROOT_EAGER}
    stack = [package, *_ROOT_EAGER]
    while stack:
        for target in ALLOWED.get(stack.pop(), frozenset()):
            root = target.split(".")[0]
            if root not in seen:
                seen.add(root)
                stack.append(root)
    return frozenset(seen)


_FRESH_IMPORT = """\
import importlib, pkgutil, sys
package = importlib.import_module("archlux." + sys.argv[1])
# A lazy facade loads almost nothing on `import`: also load every submodule and resolve
# every public name, so the check sees what the package can actually pull in.
for info in pkgutil.walk_packages(getattr(package, "__path__", []), package.__name__ + "."):
    # torch-only, optional (TORCH_TOLERATED); `appris` is its deprecated module name (ADR 0001)
    if info.name not in {"archlux.light.learned", "archlux.light.appris"}:
        importlib.import_module(info.name)
for name in getattr(package, "__all__", []):
    getattr(package, name)
print(",".join(sorted(m for m in sys.modules if m.startswith("archlux.") or m == "torch")))
"""


def _fresh_import(package: str) -> frozenset[str]:
    """Modules (``archlux.*`` and ``torch``) loaded by a fresh, exhaustive import."""
    result = subprocess.run(
        [sys.executable, "-c", _FRESH_IMPORT, package], capture_output=True, text=True, check=False
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
    # them directly (the static ALLOWED walk forbids that) and loads no light
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


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_a_fresh_import_breaks_no_forbidden_rule(package: str) -> None:
    """Each §5 FORBIDDEN rule, against ``sys.modules`` after a fresh exhaustive import."""
    prefixes, allowed = FORBIDDEN[package]
    broken = sorted(
        m for m in _fresh_import(package) if m not in allowed and any(_hits(m, p) for p in prefixes)
    )
    assert not broken, f"import archlux.{package} loads forbidden {broken} (ARCHITECTURE.md §5)"


@pytest.mark.parametrize("package", sorted(p for p in ALLOWED if p != "__init__"))
def test_a_fresh_import_loads_no_bench_and_no_torch(package: str) -> None:
    """No package but ``bench`` loads ``bench``; none loads ``torch`` (``learned`` aside)."""
    loaded = _fresh_import(package)
    assert "torch" not in loaded
    if package != "bench":
        assert not any(_hits(m, "archlux.bench") for m in loaded)


def test_feasibility_reaches_light_and_uq_only_through_api() -> None:
    """The §5 exception for ``feasibility`` is exactly "through ``api``", nothing more."""
    extra = _fresh_import("feasibility") - _fresh_import("api")
    assert all(_hits(m, "archlux.feasibility") for m in extra), sorted(extra)


@pytest.mark.parametrize("package", sorted(p for p in ALLOWED if p != "__init__"))
def test_a_fresh_import_loads_only_the_declared_layers(package: str) -> None:
    """The static AST walk above cannot see a dynamic ``importlib.import_module`` call,
    or a transitive import the declared sets did not anticipate (PLAN.md phase 4,
    block 1: a *dynamic*, ``sys.modules``-based check, alongside the static one).

    ``__init__`` (the root package) is excluded: its own laziness is already checked,
    more precisely, by ``test_import_cost.py``.
    """
    allowed_layers = _closure(package)
    for module in sorted(_fresh_import(package) - {"torch"}):
        module = module.removeprefix("archlux.")
        root = module.split(".")[0]
        if root in LEAVES or root in allowed_layers:
            continue
        pytest.fail(
            f"import archlux.{package} actually loads archlux.{module}, not reachable "
            f"through ALLOWED[{package!r}] = {sorted(ALLOWED[package])}"
        )
