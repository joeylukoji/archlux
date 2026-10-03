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
DOCS = ROOT / "docs"
_FRENCH_SUFFIX = ".fr.md"
"""The French translation of ``docs/x/page.md`` is ``docs/x/page.fr.md`` (bilingual site,
``docs/specification/DOCUMENTATION.md``). Its code blocks are those of the English page,
so it is not run twice: it is compared block by block instead."""


def _english(pages: list[Path]) -> list[Path]:
    return [page for page in pages if not page.name.endswith(_FRENCH_SUFFIX)]


def _french_sibling(page: Path) -> Path:
    return page.with_name(page.name.removesuffix(".md") + _FRENCH_SUFFIX)


USER_FACING = (
    ROOT / "README.md",
    DOCS / "index.md",
    *_english(sorted((DOCS / "gallery").glob("*.md"))),
    *_english(sorted((DOCS / "tutorials").glob("*.md"))),
    *_english(sorted((DOCS / "concepts").glob("*.md"))),
)
TRANSLATED = (
    DOCS / "index.md",
    DOCS / "installation.md",
    *_english(sorted((DOCS / "gallery").glob("*.md"))),
    *_english(sorted((DOCS / "tutorials").glob("*.md"))),
    *_english(sorted((DOCS / "concepts").glob("*.md"))),
    *_english(sorted((DOCS / "formulas").glob("*.md"))),
    *_english(sorted((DOCS / "data").glob("*.md"))),
    DOCS / "release-1.0.md",
    DOCS / "limitations.md",
    DOCS / "contributing.md",
    DOCS / "reference" / "schema-json.md",
)
"""English pages that must have a French translation next to them. The API reference,
the glossary, the specification, the ADRs and the reviews stay English only."""

_PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)
_FENCED_BLOCK = re.compile(
    r"^(?P<indent>[ \t]*)(?P<fence>```+|~~~+)[^\n]*\n.*?^(?P=indent)(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)

KNOWN_BROKEN: dict[str, tuple[type[BaseException], str]] = {}
"""Relative page path -> (expected exception, why it does not run yet).

Naming the exception keeps an unrelated breakage from hiding behind the xfail. Empty
since 2026-09-24: the five pages listed on 2026-09-23 run (PLAN.md, exit gate of
phase 1). A new entry needs a reason and a plan to remove it."""


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


def test_every_translated_page_has_a_french_version() -> None:
    """A translation cannot go missing silently: each listed page has its ``.fr.md``."""
    missing = [_id(page) for page in TRANSLATED if not _french_sibling(page).is_file()]
    assert not missing, f"English pages without a French translation: {missing}"


def _translated_pairs() -> list[object]:
    # README.fr.md is a summary of README.md, not a page of the site: out of scope.
    pages = sorted(page for page in {*USER_FACING, *TRANSLATED} if page.is_relative_to(DOCS))
    return [pytest.param(page, id=_id(page)) for page in pages if _french_sibling(page).is_file()]


@pytest.mark.parametrize("page", _translated_pairs())
def test_french_version_has_the_same_code_blocks(page: Path) -> None:
    """Code is not translated: the fenced blocks of ``page.fr.md`` are those of ``page.md``,
    verbatim and in the same order, so the run of the English page covers both."""
    english = [m.group(0) for m in _FENCED_BLOCK.finditer(page.read_text("utf-8"))]
    french_page = _french_sibling(page)
    french = [m.group(0) for m in _FENCED_BLOCK.finditer(french_page.read_text("utf-8"))]
    assert french == english, f"{_id(french_page)} code blocks differ from {_id(page)}"
