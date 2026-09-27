"""The type-guided field rename used by wave 3 (PLAN.md 3.9).

A field name shared by several classes cannot be renamed by token. This tool renames it on
one class, lets the type checker list what broke, and fixes exactly those places.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "scripts" / "rename_field.py"

if subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True).returncode:
    pytest.skip("mypy is not installed", allow_module_level=True)

SOURCE = """\
from dataclasses import dataclass, replace


@dataclass
class Plan:
    pieces: tuple[int, ...]


@dataclass
class Other:
    pieces: int


def total(plan: Plan, other: Other) -> int:
    made = Plan(pieces=(1,))
    moved = replace(made, pieces=(2,))
    return len(plan.pieces) + other.pieces + len(moved.pieces)


def maybe(plan: Plan | None) -> int:
    return len(plan.pieces) if plan else 0
"""


@pytest.fixture(scope="module")
def tool():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("rename_field", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rename_field"] = module  # dataclasses looks its module up
    spec.loader.exec_module(module)
    return module


BROKEN = SOURCE + "\n\ndef bad(o: Other) -> int:\n    return o.missing\n"


@pytest.fixture(scope="module")
def applied(tool, tmp_path_factory):  # type: ignore[no-untyped-def]
    """One rename, applied once: the tests below read the result."""
    project = tmp_path_factory.mktemp("field_rename")
    (project / "m.py").write_text(BROKEN, encoding="utf-8")
    code = tool.main(["Plan", "--field", "pieces=rooms", "--no-config", "--apply", str(project)])
    return code, project


def test_only_the_named_class_is_renamed(applied) -> None:  # type: ignore[no-untyped-def]
    code, project = applied
    text = (project / "m.py").read_text(encoding="utf-8")
    assert code == 0
    assert "    rooms: tuple[int, ...]" in text
    assert "Plan(rooms=(1,))" in text
    assert "replace(made, rooms=(2,))" in text
    assert "len(plan.rooms)" in text
    assert "len(moved.rooms)" in text
    assert "len(plan.rooms) if plan" in text  # an attribute read through Optional
    assert "    pieces: int" in text  # the other class keeps its field
    assert "other.pieces" in text


def test_errors_about_other_classes_are_left_alone(applied) -> None:  # type: ignore[no-untyped-def]
    """``o.missing`` was already an error and is not the tool's business."""
    _, project = applied
    assert "o.missing" in (project / "m.py").read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file=", str(project / "m.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    errors = [line for line in result.stdout.splitlines() if ": error:" in line]
    assert len(errors) == 1
    assert '"Other" has no attribute "missing"' in errors[0]


def test_a_dry_run_writes_nothing(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "m.py").write_text(SOURCE, encoding="utf-8")
    args = ["Plan", "--field", "pieces=rooms", "--no-config", str(tmp_path)]
    assert tool.main(args) == 0
    assert (tmp_path / "m.py").read_text(encoding="utf-8") == SOURCE


def test_an_unknown_class_or_field_is_refused(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "m.py").write_text(SOURCE, encoding="utf-8")
    assert tool.main(["Nope", "--field", "pieces=rooms", "--no-config", str(tmp_path)]) == 2
    assert tool.main(["Plan", "--field", "nothing=x", "--no-config", str(tmp_path)]) == 2
