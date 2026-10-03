"""Migrated modules contain no French identifier (PLAN.md 3.9, wave 0).

``test_language`` guards the prose of migrated files. This guards their *code*: a class,
function, parameter, attribute or variable named after a French term of the glossary. The
banned terms are read from ``docs/glossary.md`` (the French column, in backticks), so the
list cannot drift from the decisions written there.

``MIGRATED`` is a ratchet: it lists every module already free of French identifiers, and a
module joins it in the commit that finishes its rename. It never shrinks.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "docs" / "glossary.md"

MIGRATED: tuple[str, ...] = (
    "src/archlux/__init__.py",
    "src/archlux/_deprecation.py",
    "src/archlux/_version.py",
    "src/archlux/active/__init__.py",
    "src/archlux/active/densite.py",
    "src/archlux/active/density.py",
    "src/archlux/active/selection.py",
    "src/archlux/arrays.py",
    "src/archlux/bench/__init__.py",
    "src/archlux/bench/graines.py",
    "src/archlux/bench/seeds.py",
    "src/archlux/certify/__init__.py",
    "src/archlux/certify/borne.py",
    "src/archlux/certify/bound.py",
    "src/archlux/certify/dual.py",
    "src/archlux/certify/farkas.py",
    "src/archlux/certify/preuve.py",
    "src/archlux/certify/proof.py",
    "src/archlux/certify/rapport.py",
    "src/archlux/certify/report.py",
    "src/archlux/data/__init__.py",
    "src/archlux/data/decoupage.py",
    "src/archlux/data/splits.py",
    "src/archlux/erreurs.py",
    "src/archlux/errors.py",
    "src/archlux/export/__init__.py",
    "src/archlux/export/dxf.py",
    "src/archlux/export/survie.py",
    "src/archlux/export/survival.py",
    "src/archlux/export/wilson.py",
    "src/archlux/feasibility/__init__.py",
    "src/archlux/geom/__init__.py",
    "src/archlux/geom/diagnostic.py",
    "src/archlux/io/__init__.py",
    "src/archlux/lmo/__init__.py",
    "src/archlux/orient/__init__.py",
    "src/archlux/seeds.py",
    "src/archlux/solve/__init__.py",
    "src/archlux/tolerances.py",
    "src/archlux/types.py",
    "src/archlux/uq/__init__.py",
    "src/archlux/uq/fiabilite.py",
    "src/archlux/uq/reliability.py",
    "src/archlux/validation.py",
    "src/archlux/geom/graphe.py",
    "src/archlux/geom/graph.py",
    "src/archlux/geom/polytope.py",
    "src/archlux/geom/pavage.py",
    "src/archlux/geom/tiling.py",
    "src/archlux/geom/grid.py",
    "src/archlux/geom/grid_repair.py",
    "src/archlux/geom/rectilineaire.py",
    "src/archlux/geom/rectilinear.py",
    "src/archlux/lmo/solveur.py",
    "src/archlux/lmo/solver.py",
    "src/archlux/lmo/cuts.py",
    "src/archlux/uq/conforme.py",
    "src/archlux/uq/conformal.py",
    "src/archlux/uq/derive.py",
    "src/archlux/uq/drift.py",
    "src/archlux/uq/gestion.py",
    "src/archlux/uq/registry.py",
    "src/archlux/export/ifc.py",
    "src/archlux/export/pathologie.py",
    "src/archlux/export/pathologies.py",
    "src/archlux/export/svg.py",
    "src/archlux/data/chargeurs.py",
    "src/archlux/data/loaders.py",
    "src/archlux/data/corruption.py",
    "src/archlux/data/dedup.py",
    "src/archlux/data/imputation.py",
    "src/archlux/data/synthese.py",
    "src/archlux/data/synthetic.py",
    "src/archlux/bench/manifeste.py",
    "src/archlux/bench/manifest.py",
    "src/archlux/bench/protocole.py",
    "src/archlux/bench/protocol.py",
    "src/archlux/bench/rapport.py",
    "src/archlux/bench/report.py",
    "src/archlux/bench/run.py",
    "src/archlux/bench/stats.py",
    "src/archlux/active/boucle.py",
    "src/archlux/active/loop.py",
    "src/archlux/orient/circulaire.py",
    "src/archlux/orient/circular.py",
)

_TICKED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")


def french_terms(glossary: str) -> frozenset[str]:
    """Identifiers of the French column of every table, minus those kept unchanged.

    A row is a pair of cells (French, English), or two pairs side by side. A term is
    banned when it is written as an identifier in a French cell and does not also appear
    in the English cell of its row (``legalize`` and ``Plan`` are the same on both sides).
    """
    banned: set[str] = set()
    for line in glossary.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) < 2:
            continue
        pairs = [(0, 1)] + ([(3, 4)] if len(cells) >= 5 else [])
        for french, english in pairs:
            if english >= len(cells):
                continue
            banned |= set(_TICKED.findall(cells[french])) - set(_TICKED.findall(cells[english]))
    return frozenset(banned)


def identifiers(source: str) -> set[str]:
    """Every name a module defines or uses, as an identifier (not in strings or comments)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg | ast.keyword):
            if node.arg:
                names.add(node.arg)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name.split(".")[0])
    return names


def test_the_glossary_yields_the_terms_the_waves_will_rename() -> None:
    banned = french_terms(GLOSSARY.read_text(encoding="utf-8"))
    for term in ("Piece", "Mur", "Contexte", "Infaisable", "porteur", "pieces"):
        assert term in banned, term
    for kept in ("legalize", "Plan", "Orientation", "Structure", "trace"):
        assert kept not in banned, kept


def test_the_glossary_parser_understands_both_table_layouts() -> None:
    text = "\n".join(
        [
            "| French | English |",
            "|---|---|",
            "| `Piece` | `Room` |",
            "| `Plan` | `Plan` |",
            "| `Mur` | `Wall` | | `porteur` | `load_bearing` |",
        ]
    )
    assert french_terms(text) == {"Piece", "Mur", "porteur"}


def test_a_french_identifier_is_detected() -> None:
    banned = frozenset({"Piece", "porteur"})
    found = identifiers(
        "class Holder:\n    def make(self, piece: Piece):\n        return porteur\n"
    )
    assert found & banned == {"Piece", "porteur"}
    in_strings = identifiers('label = "Piece"  # porteur\n')
    assert not in_strings & banned


@pytest.mark.parametrize("path", MIGRATED)
def test_migrated_modules_use_no_french_identifier(path: str) -> None:
    banned = french_terms(GLOSSARY.read_text(encoding="utf-8"))
    found = identifiers((ROOT / path).read_text(encoding="utf-8")) & banned
    assert not found, f"{path}: French identifiers {sorted(found)} (see docs/glossary.md)"
