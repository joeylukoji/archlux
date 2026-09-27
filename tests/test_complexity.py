"""Cyclomatic complexity never regresses (PLAN.md phase 4, block 0).

A ratchet, the same shape as ``test_identifiers.py``'s ``MIGRATED`` list: ``MAX_VIOLATIONS``
records how many functions/methods exceed complexity 10 (radon rank D or worse starts at
21; rank C, used here, starts at 11 — PLAN.md's own threshold), and it only ever shrinks,
one block's commit at a time, until it reaches zero (phase 4's exit gate: ``radon cc src
-n C`` silent). It never grows: a new function above CC 10 fails this test immediately,
long before the whole phase is done.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from radon.complexity import cc_rank, cc_visit

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "archlux"

MAX_VIOLATIONS = 26
"""33 at the start of phase 4 (2026-09-27); block 3 brought `deduce_grid`,
`deduce_order`, `freeze_contacts`, `_coupe_verticale` and `_coupe_horizontale` under
CC 10; block 4 brought `solve` and `_solve_with_area_cuts` under CC 10. Lower it in
the same commit that brings a block under CC 10; never raise it."""


def _blocks() -> list[Any]:
    """Every function, method and class of ``src/archlux``.

    ``cc_visit`` already flattens methods to top-level entries alongside their class
    (the class itself gets its own aggregate complexity): do not also walk
    ``Class.methods``, or every method is counted twice.
    """
    found: list[Any] = []
    for path in SRC.rglob("*.py"):
        found.extend(cc_visit(path.read_text(encoding="utf-8")))
    return found


def test_no_new_function_above_complexity_ten() -> None:
    violations = [b for b in _blocks() if cc_rank(b.complexity) > "B"]
    assert len(violations) <= MAX_VIOLATIONS, (
        f"{len(violations)} functions above CC 10, expected at most {MAX_VIOLATIONS}: "
        + ", ".join(sorted(f"{v.name} ({v.complexity})" for v in violations))
    )
