"""Library functions refuse bad arguments with ``InvalidInput``, never a bare ``ValueError``.

PLAN.md 3.3: no bare ``ValueError``, no ``except Exception``. ``InvalidInput`` still is a
``ValueError``, so callers that caught it keep working, and it names the field.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from archlux import InvalidInput, Plan, Room
from archlux.data.loaders import _convert
from archlux.export.svg import sheet
from archlux.geom.diagnostic import diagnose
from archlux.light.tokens import permute_rooms
from archlux.orient.circular import (
    circular_linear_regression,
    circular_variance,
    encode,
    stratify,
)
from archlux.types import Regulation

SRC = Path(__file__).resolve().parents[2] / "src" / "archlux"
SQUARE = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))


def one_room_plan() -> Plan:
    return Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=4.0, h=4.0),),
        walls=(),
        openings=(),
        outline=SQUARE,
    )


@pytest.mark.parametrize(
    ("call", "field"),
    [
        (lambda: encode(10.0, harmoniques=0), "harmoniques"),
        (lambda: circular_variance([]), "degres"),
        (lambda: circular_linear_regression([1.0, 2.0], [1.0]), "theta"),
        (lambda: circular_linear_regression([1.0, 2.0], [1.0, 2.0]), "theta"),
        (lambda: stratify([1.0, 2.0], n_secteurs=0), "n_secteurs"),
        (lambda: sheet(()), "volets"),
        (lambda: diagnose(Plan(rooms=(), walls=(), openings=(), outline=SQUARE)), "rooms"),
        (lambda: permute_rooms(one_room_plan(), (0, 1)), "ordre"),
    ],
)
def test_bad_argument_raises_invalid_input_naming_the_field(call: object, field: str) -> None:
    with pytest.raises(InvalidInput) as raised:
        call()  # type: ignore[operator]
    assert raised.value.field == field
    assert isinstance(raised.value, ValueError)


def test_unreadable_wkt_is_a_rejection_not_a_swallowed_bug() -> None:
    """A malformed WKT rejects the apartment; any other error is a bug and propagates."""
    rejected = _convert(
        "x",
        [("area", "Bedroom", "not a wkt", "1", "site")],
        active_regulation=Regulation(min_areas=()),
        max_rooms=20,
        max_rectangles=30,
        tolerance_calage=0.1,
        tolerance_recollage=0.1,
    )
    assert rejected == "unreadable wkt"


def _nodes() -> list[tuple[str, ast.AST]]:
    """Every AST node of ``src/archlux``, with the ``file:line`` label to report it by."""
    return [
        (f"{path.relative_to(SRC)}:{getattr(node, 'lineno', 0)}", node)
        for path in sorted(SRC.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    ]


def _raised_name(node: ast.AST) -> str | None:
    """Name of the exception class of a ``raise``, if it is a plain name."""
    if not isinstance(node, ast.Raise) or node.exc is None:
        return None
    target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    return target.id if isinstance(target, ast.Name) else None


def _caught_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name):
        return node.type.id
    return None


def test_the_library_raises_no_bare_value_error_or_exception() -> None:
    hits = [where for where, node in _nodes() if _raised_name(node) in {"ValueError", "Exception"}]
    assert hits == []


def test_the_library_catches_no_bare_exception() -> None:
    hits = [
        where for where, node in _nodes() if _caught_name(node) in {"Exception", "BaseException"}
    ]
    assert hits == []
