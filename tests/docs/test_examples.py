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

KNOWN_BROKEN: dict[str, tuple[type[BaseException], str]] = {
    "docs/tutoriels/calibrer-un-substitut.md": (NameError, "uses 'modele' undefined"),
    "docs/tutoriels/entrainer-un-substitut.md": (NameError, "uses 'xs' undefined"),
    "docs/concepts/oracle-partage.md": (
        NameError,
        "illustrative fragment ('lmo', 'poly' undefined): make it runnable or "
        "present it as pseudo-code",
    ),
}
"""Relative page path -> (expected exception, why it does not run yet), 2026-09-23.

Naming the exception keeps an unrelated breakage from hiding behind the xfail. Fixed in
PLAN.md phase 1.8, where the README and tutorials are rewritten."""


def _pages() -> list[Path]:
    return [page for page in USER_FACING if _PYTHON_BLOCK.search(page.read_text("utf-8"))]


def _id(page: Path) -> str:
    return page.relative_to(ROOT).as_posix()


def _params() -> list[object]:
    params: list[object] = []
    for page in _pages():
        known = KNOWN_BROKEN.get(_id(page))
        marks = [pytest.mark.xfail(raises=known[0], reason=known[1], strict=True)] if known else []
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


def test_known_broken_pages_still_exist() -> None:
    """A renamed or deleted page must not leave an orphan entry behind."""
    collected = {_id(page) for page in _pages()}
    orphans = sorted(set(KNOWN_BROKEN) - collected)
    assert not orphans, f"KNOWN_BROKEN lists pages that are no longer collected: {orphans}"
