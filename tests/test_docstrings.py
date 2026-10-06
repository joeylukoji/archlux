"""Every callable of ``src/archlux`` documents its parameters and return value.

PLAN.md phase 4, block 17, item 48: 611 missing ``Parameters``/``Returns`` sections were
filled; this test keeps the count at zero. It runs ``numpydoc lint`` with the checks of
``[tool.numpydoc_validation]`` in ``pyproject.toml`` (PR01, RT01), so a new function
without them fails the suite, hence CI. A crash of numpydoc fails too: it must not read
as "no finding". PR01/RT01 only inspect existing docstrings, so a second test requires a
docstring on every public function, method and class.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("numpydoc")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "archlux"


def test_every_callable_documents_its_parameters_and_return() -> None:
    files = sorted(str(p) for p in SRC.rglob("*.py") if "graphify-out" not in p.parts)
    result = subprocess.run(
        [sys.executable, "-m", "numpydoc", "lint", "--config", str(ROOT), *files],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    # Only check findings ("path:line: PR01 ..."); numpydoc also warns, on stderr, about
    # the project's own section names (Guarantees, Formula...), which are not errors.
    output = result.stdout + result.stderr
    findings = [line for line in output.splitlines() if re.search(r":\d+: [A-Z]{2}\d{2} ", line)]
    assert not findings, "\n".join(findings)
    # numpydoc exits 1 when it reports findings; any other non-zero exit, or a traceback,
    # means it crashed and checked nothing: that must not pass as "no finding".
    assert result.returncode == 0 and "Traceback" not in result.stderr, output[-2000:]


def _public_definitions_without_docstring(tree: ast.Module) -> list[tuple[int, str]]:
    """Public top-level functions and classes, and public methods, with no docstring.

    Parameters
    ----------
    tree : ast.Module
        Parsed module.

    Returns
    -------
    list of tuple of (int, str)
        Line and name of each offender. Nested functions (closures of decorators) and
        names starting with ``_`` are left out, as interrogate does.
    """
    found: list[tuple[int, str]] = []
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def visit(body: list[ast.stmt], owner: str) -> None:
        for node in body:
            if not isinstance(node, definitions) or node.name.startswith("_"):
                continue
            if ast.get_docstring(node) is None:
                found.append((node.lineno, f"{owner}{node.name}"))
            if isinstance(node, ast.ClassDef):
                visit(node.body, f"{node.name}.")

    visit(tree.body, "")
    return found


def test_every_public_callable_has_a_docstring() -> None:
    offenders = [
        f"{path.relative_to(ROOT)}:{line}: {name}"
        for path in sorted(SRC.rglob("*.py"))
        for line, name in _public_definitions_without_docstring(
            ast.parse(path.read_text(encoding="utf-8"))
        )
    ]
    assert not offenders, "\n".join(offenders)


def test_the_docstring_guard_catches_an_undocumented_public_function() -> None:
    planted = ast.parse("def planted(a, b):\n    return a\n\n\ndef _private(a):\n    return a\n")
    assert _public_definitions_without_docstring(planted) == [(1, "planted")]
