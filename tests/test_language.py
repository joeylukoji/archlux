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
    "src/archlux/solve/__init__.py",
    "src/archlux/certify/__init__.py",
    "src/archlux/certify/proof.py",
    "src/archlux/certify/farkas.py",
    "src/archlux/certify/preuve.py",
    "src/archlux/solve/trace.py",
    "src/archlux/solve/frank_wolfe.py",
    "tests/unites/test_trace_aliases.py",
    "tests/unites/test_oracle_aliases.py",
    "tests/unites/test_frank_wolfe_honesty.py",
    "tests/unites/test_rational_proof.py",
    "tests/unites/test_farkas.py",
    "tests/unites/test_regime.py",
    "tests/test_language.py",
    "tests/checkers.py",
    "tests/unites/test_svg.py",
    "tests/unites/test_load_bearing.py",
    "tests/unites/test_inner_area.py",
    "tests/unites/test_surrogate_conformance.py",
    "tests/test_hygiene.py",
    "benchmarks/guarantees/scenarios.py",
    "benchmarks/guarantees/measure.py",
    "benchmarks/guarantees/test_scenarios.py",
    "tests/docs/test_examples.py",
    "tests/proprietes/test_realistic_guarantees.py",
    "tests/unites/test_tolerances.py",
    "tests/unites/test_version.py",
    "tests/unites/test_tiling_grid.py",
    "tests/unites/test_l_rooms.py",
    "tests/proprietes/test_l_room_guarantees.py",
    "docs/adr/0001-english-first.md",
    "README.md",
    "docs/specification/ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "CLAUDE.md",
    "tests/proprietes/test_json_schema.py",
    "docs/adr/0002-milestone-criteria-rewritten.md",
    "docs/revues/j1.md",
    "docs/revues/j2.md",
    "docs/revues/j3.md",
    "docs/revues/j4.md",
    "docs/revues/j5.md",
    "docs/revues/j6.md",
    "experiences/j6_active.py",
    "experiences/j6_ifc.py",
    "src/archlux/seeds.py",
    "tests/unites/test_seeds.py",
    "tests/unites/test_ifc_validation.py",
    "experiences/j5_coverage.py",
    "tests/unites/test_phase2_library.py",
    "experiences/j4_gradient.py",
    "experiences/j3_orientation.py",
    "tests/proprietes/test_milestone3_as_written.py",
    "experiences/j2_validity.py",
    "tests/proprietes/test_milestone2_as_written.py",
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
_WORDS = (
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
# Lower case or capitalized (`et`, `Et`), never all capitals: `ET` is the usual alias of
# xml.etree.ElementTree, not the French conjunction.
_FRENCH_WORDS = re.compile(
    r"\b(?:" + "|".join(f"[{w[0]}{w[0].upper()}]{w[1:]}" for w in _WORDS) + r")\b"
)
_CODE_OR_PATH = re.compile(r"`[^`]*`|[\w./-]+\.(?:md|py|json|csv|toml|yml)\b")
_LATIN_CITATION = re.compile(r"\bet al\.")
_LATEX_COMMAND = re.compile(r"\\+[A-Za-z]+")
"""``\\le``, ``\\qquad``, ``\\top``: LaTeX commands in formulas, not words."""


_ALLOWED_MARKER = "lang-ok:"
"""A line ending with ``# lang-ok: <reason>`` is exempt, e.g. a deprecated French alias
kept on purpose (ADR 0001, rule 6). The reason is mandatory and visible in review."""


def _french_markers(line: str) -> list[str]:
    if _ALLOWED_MARKER in line and line.split(_ALLOWED_MARKER, 1)[1].strip():
        return []
    # Underscores join words in identifiers: split them so that French names are seen.
    prose = _LATEX_COMMAND.sub(" ", _CODE_OR_PATH.sub(" ", line))
    prose = _LATIN_CITATION.sub(" ", prose).replace("_", " ")
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
    assert not _french_markers("import xml.etree.ElementTree as ET")
    assert not _french_markers(r"r^\top x \le \beta, \qquad")
    assert _french_markers("L" + r"e \le")  # the word before the command is seen
    assert not _french_markers("def pas(self):  # lang-ok: deprecated alias")
    assert _french_markers("def pas(self):  # lang-ok:")  # a reason is mandatory
    assert _french_markers("E" + "t l" + "e reste")
    assert not _french_markers("Fannjiang et al. (2022) use a 12 m " + chr(0xD7) + " 9 m grid.")
