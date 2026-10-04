"""Every callable of ``src/archlux`` documents its parameters and return value.

PLAN.md phase 4, block 17, item 48: 611 missing ``Parameters``/``Returns`` sections were
filled; this test keeps the count at zero. It runs ``numpydoc lint`` with the checks of
``[tool.numpydoc_validation]`` in ``pyproject.toml`` (PR01, RT01), so a new function
without them fails the suite, hence CI.
"""

from __future__ import annotations

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
