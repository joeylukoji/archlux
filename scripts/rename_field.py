"""Type-guided rename of the fields of one class (PLAN.md 3.9, wave 3).

A field name shared by several classes (``Plan.pieces`` and ``OrdreRelatif.pieces``) cannot
be renamed by token: ``scripts/rename_identifiers.py`` refuses it. This tool renames it on
**one** class and lets the type checker say what broke:

1. the field is renamed in the class body;
2. mypy runs over the given paths, with ``--check-untyped-defs``;
3. every error that names that class (an unknown attribute, an unexpected keyword of the
   constructor or of ``dataclasses.replace``) is fixed at the exact place mypy reports;
4. mypy runs again, until nothing is left to fix.

Errors about other classes are never touched, so ``Other.pieces`` keeps its name. What mypy
cannot see (an attribute read on an unannotated parameter, a name inside a string) stays
untouched: the test suite is the backstop, and the tool lists the field names it could not
prove.

Usage::

    python scripts/rename_field.py Plan --field pieces=rooms --field murs=walls \\
        src tests benchmarks experiments scripts            # dry run
    python scripts/rename_field.py Plan --field pieces=rooms --apply src tests ...
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Fix", "main", "parse_errors", "rename_in_class"]

_HEAD = r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): error: "
_ATTRIBUTE = re.compile(
    _HEAD + r'(?:Item )?"(?P<cls>\w+)"(?: of "[^"]*")? has no attribute "(?P<name>\w+)"'
)
_KEYWORD = re.compile(
    _HEAD + r'Unexpected keyword argument "(?P<name>\w+)" for (?:"replace" of )?"(?P<cls>\w+)"'
)
_MAX_ROUNDS = 8


@dataclass(frozen=True, slots=True)
class Fix:
    """One place mypy says is broken: an attribute read or a keyword argument."""

    path: Path
    line: int
    col: int  # 1-based, as mypy prints it
    name: str
    kind: str  # "attribute" or "keyword"


def parse_errors(output: str, class_name: str, fields: Sequence[str]) -> list[Fix]:
    """The mypy errors that concern ``class_name`` and one of its renamed ``fields``."""
    fixes: list[Fix] = []
    for line in output.splitlines():
        for pattern, kind in ((_ATTRIBUTE, "attribute"), (_KEYWORD, "keyword")):
            match = pattern.match(line)
            if match and match["cls"] == class_name and match["name"] in fields:
                fixes.append(
                    Fix(
                        Path(match["file"]),
                        int(match["line"]),
                        int(match["col"]),
                        match["name"],
                        kind,
                    )
                )
    return fixes


def _iter_python(paths: Sequence[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        found.extend([path] if path.is_file() else sorted(path.rglob("*.py")))
    return [p for p in found if "__pycache__" not in p.parts]


def _read_lines(path: Path) -> tuple[list[bytes], bool]:
    raw = path.read_bytes()
    return raw.replace(b"\r\n", b"\n").split(b"\n"), b"\r\n" in raw


def _write_lines(path: Path, lines: list[bytes], crlf: bool) -> None:
    data = b"\n".join(lines)
    path.write_bytes(data.replace(b"\n", b"\r\n") if crlf else data)


def _member_name(statement: ast.stmt) -> str | None:
    """The name a class-body statement defines: an annotated field, or a method."""
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        return statement.name
    target = getattr(statement, "target", None)
    if isinstance(statement, ast.AnnAssign) and isinstance(target, ast.Name):
        return target.id
    return None


def _name_position(statement: ast.stmt, lines: list[bytes]) -> tuple[int, int]:
    """(line, byte column) of the defined name, after ``def`` for a method."""
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        line = lines[statement.lineno - 1]
        return statement.lineno, line.index(statement.name.encode(), statement.col_offset)
    target = statement.target  # type: ignore[attr-defined]
    return target.lineno, target.col_offset


def rename_in_class(
    paths: Sequence[Path], class_name: str, mapping: dict[str, str], *, apply: bool
) -> list[str]:
    """Rename the fields in the body of ``class_name``.

    Returns
    -------
    list of str
        The old field names that were not found in the class (empty when all were).
    """
    missing = set(mapping)
    for path in _iter_python(paths):
        lines, crlf = _read_lines(path)
        try:
            tree = ast.parse(b"\n".join(lines))
        except SyntaxError:
            continue
        edits: list[tuple[int, int, str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for statement in node.body:
                    name = _member_name(statement)
                    if name in mapping:
                        edits.append((*_name_position(statement, lines), name, mapping[name]))
                        missing.discard(name)
        if apply and edits:
            for lineno, col, old, new in sorted(edits, reverse=True):
                line = lines[lineno - 1]
                lines[lineno - 1] = line[:col] + new.encode() + line[col + len(old.encode()) :]
            _write_lines(path, lines, crlf)
    return sorted(missing)


def _apply_fixes(fixes: Sequence[Fix], mapping: dict[str, str]) -> int:
    """Patch every fix at the position mypy reported. Returns how many were applied."""
    by_file: dict[Path, list[Fix]] = defaultdict(list)
    for fix in fixes:
        by_file[fix.path].append(fix)
    applied = 0
    for path, file_fixes in by_file.items():
        lines, crlf = _read_lines(path)
        tree = ast.parse(b"\n".join(lines))
        edits: set[tuple[int, int, str, str]] = set()
        for fix in file_fixes:
            position = _locate(tree, fix)
            if position is not None:
                edits.add((*position, fix.name, mapping[fix.name]))
        for lineno, col, old, new in sorted(edits, reverse=True):
            line = lines[lineno - 1]
            lines[lineno - 1] = line[:col] + new.encode() + line[col + len(old.encode()) :]
            applied += 1
        if edits:
            _write_lines(path, lines, crlf)
    return applied


def _locate(tree: ast.AST, fix: Fix) -> tuple[int, int] | None:
    """(line, byte column) of the name to rename, for the error mypy reported."""
    for node in ast.walk(tree):
        if (
            getattr(node, "lineno", None) != fix.line
            or getattr(node, "col_offset", -1) != fix.col - 1
        ):
            continue
        if fix.kind == "attribute" and isinstance(node, ast.Attribute) and node.attr == fix.name:
            assert node.end_lineno is not None
            assert node.end_col_offset is not None
            return node.end_lineno, node.end_col_offset - len(fix.name.encode())
        if fix.kind == "keyword" and isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == fix.name:
                    return keyword.lineno, keyword.col_offset
    return None


def _run_mypy(paths: Sequence[Path], *, no_config: bool) -> str:
    """The output of mypy over every path, **one run per path**.

    Given several roots at once, mypy stops with "Source file found twice under different
    module names" when a directory has no ``__init__.py``, and reports no type error at all.
    """
    command = [
        sys.executable,
        "-m",
        "mypy",
        "--check-untyped-defs",
        "--show-column-numbers",
        "--no-error-summary",
        "--no-pretty",
        "--ignore-missing-imports",
    ]
    if no_config:
        command.append("--config-file=")
    outputs = [
        subprocess.run([*command, str(path)], capture_output=True, text=True, check=False).stdout
        for path in paths
    ]
    return "\n".join(outputs)


def _parse_fields(pairs: Sequence[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in pairs:
        old, sep, new = pair.partition("=")
        if not sep or not old.isidentifier() or not new.isidentifier():
            raise ValueError(f"--field expects OLD=NEW identifiers, got {pair!r}")
        mapping[old] = new
    return mapping


def main(argv: Sequence[str] | None = None) -> int:
    """Command line entry point.

    Returns
    -------
    int
        0 on success, 2 if the class or a field was not found.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("class_name")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--field", action="append", default=[], required=True, metavar="OLD=NEW")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the files (without it, the class is renamed and restored to count places)",
    )
    parser.add_argument("--no-config", action="store_true", help="ignore the mypy configuration")
    args = parser.parse_args(argv)
    mapping = _parse_fields(args.field)

    missing = rename_in_class(args.paths, args.class_name, mapping, apply=False)
    if missing:
        print(
            f"refused: {args.class_name} has no field {missing} in {[str(p) for p in args.paths]}"
        )
        return 2
    if not args.apply:
        fixes = _dry_run_count(args, mapping)
        print(f"would rename {sorted(mapping)} on {args.class_name}: about {fixes} places")
        return 0

    rename_in_class(args.paths, args.class_name, mapping, apply=True)
    total = 0
    for _ in range(_MAX_ROUNDS):
        output = _run_mypy(args.paths, no_config=args.no_config)
        fixes = parse_errors(output, args.class_name, list(mapping))
        applied = _apply_fixes(fixes, mapping) if fixes else 0
        total += applied
        if not applied:
            break
    print(f"renamed {sorted(mapping)} on {args.class_name}: {total} places fixed from mypy errors")
    leftover = parse_errors(
        _run_mypy(args.paths, no_config=args.no_config), args.class_name, list(mapping)
    )
    for fix in leftover:
        print(f"unfixed: {fix.path}:{fix.line}: {fix.name}")
    return 0 if not leftover else 1


def _dry_run_count(args: argparse.Namespace, mapping: dict[str, str]) -> int:
    """How many places would be fixed, by renaming the class **in place**, then undoing it.

    The count needs mypy to see the renamed class, and mypy resolves ``archlux`` from the
    real tree, so a copy would not do: the files are edited for the length of the run and
    restored in a ``finally``. Interrupt it with care.
    """
    rename_in_class(args.paths, args.class_name, mapping, apply=True)
    try:
        output = _run_mypy(args.paths, no_config=args.no_config)
        return len(parse_errors(output, args.class_name, list(mapping)))
    finally:
        reverse = {new: old for old, new in mapping.items()}
        rename_in_class(args.paths, args.class_name, reverse, apply=True)


if __name__ == "__main__":
    raise SystemExit(main())
