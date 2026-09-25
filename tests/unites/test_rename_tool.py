"""The rename tool used by the English-API waves (PLAN.md 3.9, wave 0).

A rename is only reviewable if it is mechanical, so the tool renames identifiers (never
strings or comments unless asked), refuses names that several classes define, and can
prove that the result is the original with the names swapped back.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "scripts" / "rename_identifiers.py"


@pytest.fixture(scope="module")
def tool():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("rename_identifiers", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = '''\
from pkg import Piece

# a Piece in a comment
class Holder:
    """Holds a Piece."""

    item: Piece

    def make(self, piece: Piece) -> Piece:
        label = "Piece"
        return Piece(id=piece.id, note=f"{Piece.__name__} ok")
'''


def test_identifiers_are_renamed_but_not_strings_or_comments(tool) -> None:  # type: ignore[no-untyped-def]
    new, count = tool.rename_source(SOURCE, {"Piece": "Room"})
    assert count == 6
    assert "from pkg import Room" in new
    assert "item: Room" in new
    assert "def make(self, piece: Room) -> Room:" in new
    assert 'label = "Piece"' in new
    assert "# a Piece in a comment" in new
    assert '"""Holds a Piece."""' in new
    assert "Room(id=piece.id" in new
    assert "{Room.__name__} ok" in new


def test_keyword_arguments_and_attributes_are_renamed(tool) -> None:  # type: ignore[no-untyped-def]
    text = "plan = Plan(pieces=(), murs=())\nn = len(plan.pieces)\n"
    new, count = tool.rename_source(text, {"pieces": "rooms", "murs": "walls"})
    assert new == "plan = Plan(rooms=(), walls=())\nn = len(plan.rooms)\n"
    assert count == 3


def test_prose_renaming_is_opt_in(tool) -> None:  # type: ignore[no-untyped-def]
    new, _ = tool.rename_source(SOURCE, {"Piece": "Room"}, prose=True)
    assert "# a Room in a comment" in new
    assert '"""Holds a Room."""' in new
    assert 'label = "Piece"' in new  # a plain string literal is never touched


def test_line_endings_are_preserved(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "a.py"
    path.write_bytes(b"x = Piece()\r\ny = 1\r\n")
    tool.rename_file(path, {"Piece": "Room"}, apply=True)
    assert path.read_bytes() == b"x = Room()\r\ny = 1\r\n"


def test_a_dry_run_writes_nothing(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "a.py"
    path.write_text("x = Piece()\n", encoding="utf-8")
    changed = tool.rename_file(path, {"Piece": "Room"}, apply=False)
    assert changed == 1
    assert path.read_text(encoding="utf-8") == "x = Piece()\n"


def test_markdown_code_blocks_are_renamed_but_not_prose(tool) -> None:  # type: ignore[no-untyped-def]
    text = "A Piece is a room.\n\n```python\nx = Piece(id='a')\n```\n\nUse `Piece` here.\n"
    new, count = tool.rename_markdown(text, {"Piece": "Room"})
    assert count == 1
    assert "A Piece is a room." in new
    assert "x = Room(id='a')" in new
    assert "Use `Piece` here." in new


def test_markdown_prose_renaming_covers_inline_code(tool) -> None:  # type: ignore[no-untyped-def]
    text = "A Piece is a room.\n\nUse `Piece` here.\n"
    new, _ = tool.rename_markdown(text, {"Piece": "Room"}, prose=True)
    assert new == "A Room is a room.\n\nUse `Room` here.\n"


def test_names_defined_by_several_owners_are_reported(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "m.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\nclass Plan:\n    pieces: tuple\n"
        "@dataclass\nclass Order:\n    pieces: tuple\n"
        "@dataclass\nclass Wall:\n    porteur: bool\n",
        encoding="utf-8",
    )
    shared = tool.find_shared_names([tmp_path], {"pieces", "porteur"})
    assert set(shared) == {"pieces"}
    assert shared["pieces"] == ["Order", "Plan"]


def test_the_command_refuses_a_shared_name_unless_allowed(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "m.py").write_text(
        "class A:\n    pieces = 1\nclass B:\n    pieces = 2\n", encoding="utf-8"
    )
    args = ["--map", "pieces=rooms", "--apply", str(tmp_path)]
    assert tool.main(args) == 2
    assert "pieces" in (tmp_path / "m.py").read_text(encoding="utf-8")
    assert tool.main([*args, "--allow-shared", "pieces"]) == 0
    assert "rooms" in (tmp_path / "m.py").read_text(encoding="utf-8")


def test_verify_accepts_a_pure_rename(tool) -> None:  # type: ignore[no-untyped-def]
    new, _ = tool.rename_source(SOURCE, {"Piece": "Room"})
    assert tool.verify_inverse(SOURCE, new, {"Piece": "Room"})


def test_verify_rejects_a_change_that_is_not_a_rename(tool) -> None:  # type: ignore[no-untyped-def]
    new, _ = tool.rename_source(SOURCE, {"Piece": "Room"})
    tampered = new.replace("id=piece.id", "id=piece.name")
    assert not tool.verify_inverse(SOURCE, tampered, {"Piece": "Room"})


def test_a_mapping_that_merges_two_names_is_refused(tool) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="same new name"):
        tool.check_mapping({"Piece": "Room", "Chambre": "Room"})


def test_string_literal_hits_are_reported_not_changed(tool) -> None:  # type: ignore[no-untyped-def]
    hits = tool.string_hits('x = getattr(plan, "pieces")\ny = "other"\n', {"pieces"})
    assert hits == [(1, "pieces")]


def test_excluded_paths_are_left_alone(tool, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "a.py").write_text("x = Piece()\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y = Piece()\n", encoding="utf-8")
    args = ["--map", "Piece=Room", "--apply", "--exclude", str(tmp_path / "keep"), str(tmp_path)]
    assert tool.main(args) == 0
    assert (tmp_path / "keep" / "a.py").read_text(encoding="utf-8") == "x = Piece()\n"
    assert (tmp_path / "b.py").read_text(encoding="utf-8") == "y = Room()\n"
