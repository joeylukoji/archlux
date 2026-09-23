"""Files already migrated to English stay English (ADR 0001, PLAN.md batch E1).

``MIGRATED`` grows batch by batch; a file enters it once fully translated. The check is
deliberately simple (accented letters and common French function words) because its
job is to stop regressions, not to grade prose. Inline code and file paths are ignored:
they may legitimately name files that are not renamed yet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

MIGRATED: tuple[str, ...] = (
    "src/archlux/_version.py",
    "src/archlux/tolerances.py",
    "tests/test_language.py",
    "tests/docs/test_examples.py",
    "tests/proprietes/test_realistic_guarantees.py",
    "tests/unites/test_tolerances.py",
    "tests/unites/test_version.py",
    "docs/adr/0001-english-first.md",
)
"""Repository-relative paths that must contain no French prose."""

# Patterns are written with escapes and split literals so that this checker does not
# flag its own source.
# Latin-1 letters, minus the multiplication and division signs used in English prose.
_ACCENTED = re.compile(
    "["
    + chr(0xC0)
    + "-"
    + chr(0xD6)
    + chr(0xD8)
    + "-"
    + chr(0xF6)
    + chr(0xF8)
    + "-"
    + chr(0xFF)
    + chr(0x152)
    + chr(0x153)
    + chr(0x178)
    + "]"
)
_FRENCH_WORDS = re.compile(
    r"\b("
    + "|".join(
        (
            "l" + "e",
            "l" + "a",
            "l" + "es",
            "d" + "es",
            "u" + "ne",
            "e" + "st",
            "s" + "ont",
            "p" + "our",
            "a" + "vec",
            "d" + "ans",
            "s" + "ans",
            "m" + "ais",
            "d" + "onc",
            "q" + "ui",
            "q" + "ue",
            "p" + "as",
            "s" + "ur",
            "a" + "ux",
            "d" + "u",
            "c" + "ette",
            "l" + "eur",
            "f" + "ait",
            "d" + "e",
            "e" + "t",
            "u" + "n",
        )
    )
    + r")\b",
    re.IGNORECASE,
)
_CODE_OR_PATH = re.compile(r"`[^`]*`|[\w./-]+\.(?:md|py|json|csv|toml|yml)\b")
_LATIN_CITATION = re.compile(r"\bet al\.")


def _french_markers(line: str) -> list[str]:
    # Underscores join words in identifiers: split them so that French names are seen.
    prose = _LATIN_CITATION.sub(" ", _CODE_OR_PATH.sub(" ", line)).replace("_", " ")
    return _ACCENTED.findall(prose) + _FRENCH_WORDS.findall(prose)


@pytest.mark.parametrize("relative", MIGRATED)
def test_migrated_files_contain_no_french(relative: str) -> None:
    path = ROOT / relative
    offending = [
        f"{relative}:{number}: {sorted(set(markers))} in {line.strip()[:80]!r}"
        for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1)
        if (markers := _french_markers(line))
    ]
    assert not offending, "French prose in a migrated file:\n" + "\n".join(offending)


def test_every_migrated_path_exists() -> None:
    missing = [p for p in MIGRATED if not (ROOT / p).is_file()]
    assert not missing, f"MIGRATED lists files that do not exist: {missing}"


def test_the_checker_detects_french() -> None:
    """Guard against a checker that silently accepts everything."""
    assert _french_markers("L" + "e solveur ren" + "d u" + "n plan valide.")
    assert _french_markers("surface minimale " + chr(0xE9) + "chou" + chr(0xE9) + "e")
    assert not _french_markers("The solver returns a valid plan.")
    assert not _french_markers("reads `docs/tutoriels/premiers-pas.md` again")
    assert _french_markers("def test_l" + "e_certificat_affiche_l" + "a_version() -> None:")
    assert not _french_markers("Fannjiang et al. (2022) use a 12 m " + chr(0xD7) + " 9 m grid.")
