"""The 26 modules renamed in chantier E, wave 1a, stay importable under their old path.

ADR 0001, rule 6: an old module path is a deprecated shim until 1.0.0. Through it, every
public name of the new module and every former French name the new module still serves
resolve to the same object, with a ``DeprecationWarning`` naming the new path. Old
pickles, which name a class by its old module path, still load.
"""

from __future__ import annotations

import ast
import importlib
import pickle
import warnings
from pathlib import Path

import pytest

from tests.unit.test_function_aliases import ALIASES

RENAMED: dict[str, str] = {
    "archlux.active.boucle": "archlux.active.loop",
    "archlux.bench.graines": "archlux.bench.seeds",
    "archlux.bench.manifeste": "archlux.bench.manifest",
    "archlux.bench.protocole": "archlux.bench.protocol",
    "archlux.bench.rapport": "archlux.bench.report",
    "archlux.certify.borne": "archlux.certify.bound",
    "archlux.certify.rapport": "archlux.certify.report",
    "archlux.data.chargeurs": "archlux.data.loaders",
    "archlux.data.decoupage": "archlux.data.splits",
    "archlux.data.synthese": "archlux.data.synthetic",
    "archlux.export.pathologie": "archlux.export.pathologies",
    "archlux.geom.graphe": "archlux.geom.graph",
    "archlux.geom.pavage": "archlux.geom.tiling",
    "archlux.geom.rectilineaire": "archlux.geom.rectilinear",
    "archlux.light.analytique": "archlux.light.analytic",
    "archlux.light.appris": "archlux.light.learned",
    "archlux.light.jetons": "archlux.light.tokens",
    "archlux.light.objectif": "archlux.light.objective",
    "archlux.light.protocole": "archlux.light.protocol",
    "archlux.light.simulateur": "archlux.light.split_flux",
    "archlux.lmo.solveur": "archlux.lmo.solver",
    "archlux.orient.circulaire": "archlux.orient.circular",
    "archlux.uq.conforme": "archlux.uq.conformal",
    "archlux.uq.derive": "archlux.uq.drift",
    "archlux.uq.fiabilite": "archlux.uq.reliability",
    "archlux.uq.gestion": "archlux.uq.registry",
}
"""Old module path to new module path (docs/glossary.md, "Modules and files")."""

SRC = Path(__file__).resolve().parents[2] / "src" / "archlux"

FRENCH_THROUGH_SHIM = [
    (old_module, new_module, old, new)
    for old_module, new_module in RENAMED.items()
    for module, old, new in ALIASES
    if module == new_module
]
"""Every ``test_function_aliases`` row of a renamed module, replayed through its old path."""


@pytest.mark.parametrize(("old_module", "new_module"), sorted(RENAMED.items()))
def test_the_old_path_serves_the_new_module_and_warns(old_module: str, new_module: str) -> None:
    legacy = importlib.import_module(old_module)
    current = importlib.import_module(new_module)
    name = current.__all__[0]
    match = f"{old_module}.{name} is deprecated, use {new_module}.{name}"
    with pytest.warns(DeprecationWarning, match=match.replace(".", r"\.")):
        value = getattr(legacy, name)
    assert value is getattr(current, name)
    assert legacy.__all__ == []


@pytest.mark.parametrize(("old_module", "new_module"), sorted(RENAMED.items()))
def test_every_public_name_is_served(old_module: str, new_module: str) -> None:
    legacy = importlib.import_module(old_module)
    current = importlib.import_module(new_module)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for name in current.__all__:
            assert getattr(legacy, name) is getattr(current, name), name


@pytest.mark.parametrize(("old_module", "new_module", "old", "new"), FRENCH_THROUGH_SHIM)
def test_a_former_french_name_still_resolves_through_the_old_path(
    old_module: str, new_module: str, old: str, new: str
) -> None:
    legacy = importlib.import_module(old_module)
    match = f"{old_module}.{old} is deprecated, use {new_module}.{new}"
    with pytest.warns(DeprecationWarning, match=match.replace(".", r"\.")):
        value = getattr(legacy, old)
    assert value is getattr(importlib.import_module(new_module), new)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(f"from {old_module} import {old}", {})
    assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1


def test_the_french_rows_cover_the_shims() -> None:
    """Guard against the replay above silently matching nothing."""
    assert len({row[0] for row in FRENCH_THROUGH_SHIM}) >= 20


def test_an_unknown_name_raises_attribute_error() -> None:
    legacy = importlib.import_module("archlux.geom.pavage")
    with pytest.raises(AttributeError, match=r"archlux\.geom\.pavage"):
        legacy.NoSuchName  # noqa: B018


def test_an_old_pickle_naming_the_old_module_still_loads() -> None:
    """Protocol 0 writes the module path as text: swap in the old one, as an old pickle."""
    from archlux.uq.registry import CalibrationToken

    token = CalibrationToken(weights_fingerprint="w", freeze_timestamp="t", signature="s")
    payload = pickle.dumps(token, protocol=0)
    old_payload = payload.replace(b"archlux.uq.registry", b"archlux.uq.gestion")
    assert old_payload != payload
    with pytest.warns(DeprecationWarning, match=r"use archlux\.uq\.registry\.CalibrationToken"):
        assert pickle.loads(old_payload) == token


def test_nothing_in_the_library_imports_a_shim() -> None:
    """A shim is for callers outside archlux: the library itself uses the new paths only."""
    offenders = []
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module in RENAMED:
                offenders.append(f"{path.relative_to(SRC)}: {node.module}")
            elif isinstance(node, ast.Import):
                offenders += [
                    f"{path.relative_to(SRC)}: {a.name}" for a in node.names if a.name in RENAMED
                ]
    assert not offenders
