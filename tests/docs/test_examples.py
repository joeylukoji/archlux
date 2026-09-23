"""Every Python example a user can copy from the documentation must run.

Scope: the pages a user reads to *use* the library — README, home page, gallery,
tutorials and concepts. Specification pages (``docs/specification/``) are design
documents made of signatures and pseudo-code; they are deliberately out of scope.

Each page is executed as a narrative: its ``python`` blocks run in order, in one shared
namespace, inside a temporary directory so that written files never touch the
repository.

Pages that are known to be broken are listed in ``KNOWN_BROKEN`` with the reason. They
are marked ``xfail(strict=True)``: once a fix makes a page run, the test fails until the
entry is removed, so this list can only shrink (PLAN.md, task 0.7).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
USER_FACING = (
    ROOT / "README.md",
    ROOT / "docs" / "index.md",
    *sorted((ROOT / "docs" / "galerie").glob("*.md")),
    *sorted((ROOT / "docs" / "tutoriels").glob("*.md")),
    *sorted((ROOT / "docs" / "concepts").glob("*.md")),
)
_PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)

KNOWN_BROKEN: dict[str, str] = {
    "README.md": (
        "reads a missing 'sortie_generateur.json'; calls APIs that do not exist "
        "(Structure.from_dxf, ax.referentiel, Daylight(metric=), "
        "data.generator_outputs, Contexte.sweep_orientation) — AUDIT.md §3 n°2"
    ),
    "docs/index.md": "reads a missing 'sortie_generateur.json'",
    "docs/tutoriels/premiers-pas.md": "reads a missing 'sortie_generateur.json'",
    "docs/tutoriels/calibrer-un-substitut.md": "uses 'modele' without defining it",
    "docs/tutoriels/entrainer-un-substitut.md": "uses 'xs' without defining it",
    "docs/concepts/oracle-partage.md": (
        "illustrative fragment ('lmo', 'poly' undefined): make it runnable or "
        "present it as pseudo-code"
    ),
}
"""Relative page path -> why it does not run yet (state of 2026-09-23).

Fixed in PLAN.md phase 1.8, where the README and tutorials are rewritten."""


def _pages() -> list[Path]:
    return [page for page in USER_FACING if _PYTHON_BLOCK.search(page.read_text("utf-8"))]


def _id(page: Path) -> str:
    return page.relative_to(ROOT).as_posix()


def _params() -> list[object]:
    params: list[object] = []
    for page in _pages():
        reason = KNOWN_BROKEN.get(_id(page))
        marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
        params.append(pytest.param(page, id=_id(page), marks=marks))
    return params


@pytest.mark.parametrize("page", _params())
def test_documentation_examples_run(
    page: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All ``python`` blocks of ``page`` run, in order, without raising."""
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {"__name__": "__doc_example__"}
    blocks = _PYTHON_BLOCK.findall(page.read_text("utf-8"))
    for index, source in enumerate(blocks, start=1):
        code = compile(source, f"{_id(page)} [block {index}/{len(blocks)}]", "exec")
        exec(code, namespace)  # executing our own documentation is the point
