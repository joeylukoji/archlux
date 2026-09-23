"""Tracked text files contain no invisible control characters.

A mistyped escape in a script (``\b``, ``\f``) silently writes a backspace or a form
feed into a file; the result still parses and renders almost right. This happened three
times while writing PLAN.md phases 0 and 1.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".cff", ".txt", ".json", ".svg"}
_ALLOWED = {0x09, 0x0A, 0x0D}  # tab, line feed, carriage return


def _tracked_text_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=ROOT, check=False
    ).stdout.splitlines()
    return [ROOT / name for name in listed if Path(name).suffix in _TEXT_SUFFIXES]


def test_no_tracked_text_file_contains_a_control_character() -> None:
    files = _tracked_text_files()
    if not files:
        pytest.skip("not a git checkout")
    offending = []
    for path in files:
        if not path.is_file():
            continue
        data = path.read_bytes()
        bad = sorted({byte for byte in data if byte < 0x20 and byte not in _ALLOWED})
        if bad:
            offending.append(f"{path.relative_to(ROOT)}: {[hex(b) for b in bad]}")
    assert not offending, "control characters found:\n" + "\n".join(offending)
