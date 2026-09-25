"""Mechanical identifier renames for the English-API waves (PLAN.md 3.9, wave 0).

A rename is only reviewable when it is mechanical. This tool renames Python identifiers
by token, never by text search, so strings and comments are left alone unless asked, and
it proves its own work:

- **identifiers only**: every ``NAME`` token equal to an old name is renamed, wherever it
  is a class, a function, an attribute, a keyword argument or an f-string expression;
  string literals and comments are untouched (``--prose`` also renames comments,
  docstrings and the prose of markdown files);
- **refuses to guess**: an old name defined by several classes or functions (for instance
  a field ``pieces`` on three classes) is reported and nothing is written, unless the name
  is listed with ``--allow-shared``;
- **verifies**: the renamed source, with the names swapped back, must have the same syntax
  tree as the original (``--no-verify`` turns it off). Equal trees prove a pure rename;
- **dry run by default**: without ``--apply`` nothing is written.

Python code blocks of markdown files are renamed like Python files. Line endings are
preserved. The tokenizer of Python 3.12 or newer is required: it exposes the expressions
inside f-strings, which older versions hide in one string token.

Examples
--------
::

    python scripts/rename_identifiers.py --map Piece=Room src tests docs
    python scripts/rename_identifiers.py --map Piece=Room --apply src tests docs
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from collections import defaultdict
from collections.abc import Iterator, Sequence
from pathlib import Path

__all__ = [
    "check_mapping",
    "find_shared_names",
    "main",
    "rename_file",
    "rename_markdown",
    "rename_source",
    "string_hits",
    "verify_inverse",
]

SKIPPED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".claude",
        ".kilo",
        "site",
        ".hypothesis",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "build",
        "dist",
    }
)
_FENCE = re.compile(r"^(?P<indent>\s*)(?P<marks>`{3,}|~{3,})\s*(?P<lang>\w*)\s*$")
_TOKENIZE_ERRORS = (SyntaxError, tokenize.TokenError, IndentationError)
_Edit = tuple[int, int, int, str, int]  # row, column, length, replacement, names replaced


def check_mapping(mapping: dict[str, str]) -> None:
    """Refuse a mapping that would merge two names or chain a rename into another.

    Raises
    ------
    ValueError
        Two old names map to the same new name, or a new name is also an old name.
    """
    seen: dict[str, str] = {}
    for old, new in mapping.items():
        if new in seen:
            raise ValueError(f"{seen[new]!r} and {old!r} have the same new name {new!r}")
        seen[new] = old
    chained = sorted(set(mapping) & set(mapping.values()))
    if chained:
        raise ValueError(f"names both renamed and produced by a rename: {chained}")


def _word_sub(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    """Word-boundary replacement of every old name in free text."""
    if not mapping:
        return text, 0
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, mapping)) + r")\b")
    return pattern.subn(lambda match: mapping[match.group(1)], text)


def _docstring_starts(tree: ast.AST) -> set[tuple[int, int]]:
    """Positions of the docstrings of a module, its classes and its functions."""
    starts: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                starts.add((first.lineno, first.col_offset))
    return starts


def _prose_edits(token: tokenize.TokenInfo, mapping: dict[str, str]) -> Iterator[_Edit]:
    """Edits inside a comment or a docstring, one per line it changes."""
    row, col = token.start
    for k, piece in enumerate(token.string.split("\n")):
        replaced, n = _word_sub(piece, mapping)
        if n:
            yield row + k, col if k == 0 else 0, len(piece), replaced, n


def rename_source(text: str, mapping: dict[str, str], *, prose: bool = False) -> tuple[str, int]:
    """Rename the identifiers of one Python source.

    Parameters
    ----------
    text : str
        Python source, with ``\\n`` line endings.
    mapping : dict of str to str
        Old identifier to new identifier.
    prose : bool, optional
        Also rename, on word boundaries, inside comments and docstrings. Other string
        literals are never touched.

    Returns
    -------
    tuple of (str, int)
        The new source and the number of names replaced.
    """
    if sys.version_info < (3, 12):
        raise RuntimeError("rename_identifiers needs Python 3.12+ (f-string tokens)")
    if not mapping:
        return text, 0
    docstrings = _docstring_starts(ast.parse(text)) if prose else set()
    edits: list[_Edit] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        row, col = token.start
        if token.type == tokenize.NAME and token.string in mapping:
            edits.append((row, col, len(token.string), mapping[token.string], 1))
        elif prose and (
            token.type == tokenize.COMMENT
            or (token.type == tokenize.STRING and (row, col) in docstrings)
        ):
            edits.extend(_prose_edits(token, mapping))
    lines = text.split("\n")
    for row, col, length, replacement, _ in sorted(edits, reverse=True):
        line = lines[row - 1]
        lines[row - 1] = line[:col] + replacement + line[col + length :]
    return "\n".join(lines), sum(edit[4] for edit in edits)


def _rename_block(
    block: list[str], indent: str, mapping: dict[str, str], prose: bool
) -> tuple[list[str], int]:
    """Rename a python code block, undoing and redoing its indentation."""
    stripped = [line[len(indent) :] if line.startswith(indent) else line for line in block]
    try:
        new, n = rename_source("\n".join(stripped), mapping, prose=prose)
    except _TOKENIZE_ERRORS:
        return block, 0
    return [indent + line if line else line for line in new.split("\n")], n


def rename_markdown(text: str, mapping: dict[str, str], *, prose: bool = False) -> tuple[str, int]:
    """Rename identifiers in the ``python`` code blocks of a markdown text.

    Prose and inline code are renamed only with ``prose=True``. A code block that does
    not tokenize is left unchanged.

    Returns
    -------
    tuple of (str, int)
        The new text and the number of names replaced.
    """
    out: list[str] = []
    total = 0
    fence: re.Match[str] | None = None
    block: list[str] = []
    for line in text.split("\n"):
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence, block = match, []
            elif prose:
                line, n = _word_sub(line, mapping)
                total += n
            out.append(line)
            continue
        closes = match is not None and not match["lang"] and match["marks"][0] == fence["marks"][0]
        if not closes:
            block.append(line)
            continue
        if fence["lang"].lower() in {"python", "py"}:
            block, n = _rename_block(block, fence["indent"], mapping, prose)
            total += n
        out.extend([*block, line])
        fence = None
    if fence is not None:  # an unterminated fence: keep its content as it was
        out.extend(block)
    return "\n".join(out), total


def _iter_files(
    paths: Sequence[Path], suffixes: tuple[str, ...], exclude: Sequence[Path] = ()
) -> Iterator[Path]:
    excluded = [path.resolve() for path in exclude]
    for path in paths:
        candidates = [path] if path.is_file() else sorted(path.rglob("*"))
        for candidate in candidates:
            parts = set(candidate.relative_to(path).parts) if candidate != path else set()
            resolved = candidate.resolve()
            skipped = bool(SKIPPED_DIRS & parts) or any(
                resolved == out or out in resolved.parents for out in excluded
            )
            if candidate.is_file() and candidate.suffix in suffixes and not skipped:
                yield candidate


def _read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def _rename(path: Path, text: str, mapping: dict[str, str], prose: bool) -> tuple[str, int]:
    if path.suffix == ".md":
        return rename_markdown(text, mapping, prose=prose)
    return rename_source(text, mapping, prose=prose)


def rename_file(path: Path, mapping: dict[str, str], *, apply: bool, prose: bool = False) -> int:
    """Rename one file (``.py`` or ``.md``), keeping its line endings.

    Returns
    -------
    int
        The number of names replaced. The file is written only if ``apply`` is true.
    """
    text, crlf = _read(path)
    try:
        new, count = _rename(path, text, mapping, prose)
    except _TOKENIZE_ERRORS:
        return 0
    if apply and count:
        path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    return count


def verify_inverse(
    original: str, renamed: str, mapping: dict[str, str], *, prose: bool = False
) -> bool:
    """Whether ``renamed`` is ``original`` with the names swapped, and nothing else.

    The names are swapped back and the two syntax trees compared. A rename that also
    changed behaviour, or that captured a name already used, does not pass.
    """
    inverse = {new: old for old, new in mapping.items()}
    try:
        back, _ = rename_source(renamed, inverse, prose=prose)
        return ast.dump(ast.parse(original)) == ast.dump(ast.parse(back))
    except _TOKENIZE_ERRORS:
        return False


def find_shared_names(
    paths: Sequence[Path], names: set[str], exclude: Sequence[Path] = ()
) -> dict[str, list[str]]:
    """Names that several classes or functions define: renaming them is a guess.

    An owner is a class that declares the name as a field, a class attribute, a method or
    ``self.name = ...``, or a function that takes it as a parameter.

    Returns
    -------
    dict of str to list of str
        For every name defined by more than one owner, the sorted owner names.
    """
    owners: dict[str, set[str]] = defaultdict(set)
    for path in _iter_files(paths, (".py",), exclude):
        try:
            tree = ast.parse(_read(path)[0])
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for name in _defined_in_class(node) & names:
                    owners[name].add(node.name)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                args = node.args
                every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
                for name in {arg.arg for arg in every} & names:
                    owners[name].add(f"{node.name}()")
    return {name: sorted(found) for name, found in owners.items() if len(found) > 1}


def _defined_in_class(node: ast.ClassDef) -> set[str]:
    defined: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            defined.add(child.target.id)
        elif isinstance(child, ast.Assign):
            defined.update(t.id for t in child.targets if isinstance(t, ast.Name))
        elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Store):
            if isinstance(child.value, ast.Name) and child.value.id == "self":
                defined.add(child.attr)
        elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            defined.add(child.name)
    return defined


def string_hits(text: str, names: set[str]) -> list[tuple[int, str]]:
    """String literals that are exactly an old name, such as ``getattr(x, "pieces")``.

    They are reported, never changed: the tool cannot know that the string names an
    attribute. Docstrings are not reported.
    """
    docstrings = _docstring_starts(ast.parse(text))
    hits: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.STRING and token.start not in docstrings:
            content = token.string.strip("'\"")
            if content in names:
                hits.append((token.start[0], content))
    return hits


def _parse_mapping(pairs: Sequence[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in pairs:
        old, sep, new = pair.partition("=")
        if not sep or not old.isidentifier() or not new.isidentifier():
            raise ValueError(f"--map expects OLD=NEW identifiers, got {pair!r}")
        mapping[old] = new
    return mapping


def main(argv: Sequence[str] | None = None) -> int:
    """Command line entry point.

    Returns
    -------
    int
        0 on success, 2 if a shared name was refused, 3 if the verification failed.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--map", action="append", default=[], metavar="OLD=NEW", required=True)
    parser.add_argument("--apply", action="store_true", help="write the files")
    parser.add_argument("--prose", action="store_true", help="also comments, docstrings, markdown")
    parser.add_argument("--allow-shared", action="append", default=[], metavar="NAME")
    parser.add_argument("--no-verify", action="store_true", help="skip the inverse-rename proof")
    parser.add_argument("--exclude", action="append", default=[], type=Path, metavar="PATH")
    args = parser.parse_args(argv)

    mapping = _parse_mapping(args.map)
    check_mapping(mapping)
    shared = find_shared_names(args.paths, set(mapping) - set(args.allow_shared), args.exclude)
    if shared:
        for name, owners in sorted(shared.items()):
            print(f"refused: {name!r} is defined by {', '.join(owners)}")
        print("nothing written; rename these by hand, or list them with --allow-shared")
        return 2

    total = files = 0
    for path in _iter_files(args.paths, (".py", ".md"), args.exclude):
        text, _ = _read(path)
        try:
            new, count = _rename(path, text, mapping, args.prose)
        except _TOKENIZE_ERRORS:
            continue
        if not count:
            continue
        proved = path.suffix != ".py" or args.no_verify
        if not proved and not verify_inverse(text, new, mapping, prose=args.prose):
            print(f"verification failed: {path} (not a pure rename)")
            return 3
        if path.suffix == ".py":
            for line, name in string_hits(text, set(mapping)):
                print(f"warning: {path}:{line}: string {name!r} not renamed")
        total += count
        files += 1
        rename_file(path, mapping, apply=args.apply, prose=args.prose)
    verb = "renamed" if args.apply else "would rename"
    print(f"{verb} {total} names in {files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
