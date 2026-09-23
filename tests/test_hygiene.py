"""Tracked text files contain no invisible control characters.

A mistyped escape in a script (``\\b``, ``\\f``) silently writes a backspace or a form
feed into a file; the result still parses and renders almost right. This happened three
times while writing PLAN.md phases 0 and 1.

Every tracked file is checked unless it is binary (it contains a NUL byte), whatever its
extension: ``.csv``, ``LICENSE`` or ``.gitignore`` are text too.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALLOWED = {0x09, 0x0A, 0x0D}  # tab, line feed, carriage return


def _tracked_files() -> list[Path]:
    try:
        listed = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=ROOT, check=False
        ).stdout.splitlines()
    except FileNotFoundError:  # git is not installed
        return []
    return [ROOT / name for name in listed]


def test_no_tracked_text_file_contains_a_control_character() -> None:
    files = [path for path in _tracked_files() if path.is_file()]
    if not files:
        pytest.skip("not a git checkout, or git is not installed")
    offending = []
    for path in files:
        data = path.read_bytes()
        if b"\x00" in data:
            continue  # binary file
        bad = sorted({byte for byte in data if byte < 0x20 and byte not in _ALLOWED})
        if bad:
            offending.append(f"{path.relative_to(ROOT)}: {[hex(b) for b in bad]}")
    assert not offending, "control characters found:\n" + "\n".join(offending)
