"""Milestone-8 bench (``archlux.bench.generation``, PLAN.md phase 4, block 16)."""

from __future__ import annotations

import pytest

import archlux as ax
from archlux.bench.generation import (
    BUDGETS,
    FIELDS,
    WIDTHS,
    evaluate_generated,
    summarize_generation,
)
from archlux.errors import (
    GapNeedsTiling,
    GridNotRecoverable,
    Infeasible,
    InvariantViolation,
)
from archlux.types import Context, Plan

# Overlapping rooms: invalid as generated, so every sweep has something to repair.
RECORD = {
    "id": "g0",
    "pieces": [
        {"type": "living_room", "coins": [[0, 0], [3, 0], [3, 2], [0, 2]]},
        {"type": "bedroom", "coins": [[2.5, 0], [5, 0], [5, 2], [2.5, 2]]},
    ],
    "programme": ["living_room", "bedroom"],
}


def test_one_row_per_run_with_the_published_columns() -> None:
    rows = evaluate_generated(RECORD, 1.0, legalize=ax.legalize)
    assert not isinstance(rows, str)
    # Baseline and every budget at the nominal width, then the largest budget per width.
    assert len(rows) == 1 + len(BUDGETS) + len(WIDTHS)
    assert all(set(row) == set(FIELDS) for row in rows)
    assert {row["valid_before"] for row in rows} == {False}


def test_a_degenerate_record_is_rejected_with_its_reason() -> None:
    flat = {**RECORD, "pieces": [{"type": "bedroom", "coins": [[0, 0], [1, 0], [1, 0], [0, 0]]}]}
    assert evaluate_generated(flat, 1.0, legalize=ax.legalize) == "degenerate room"


def test_the_summary_reads_back_the_csv_strings() -> None:
    rows = evaluate_generated(RECORD, 1.0, legalize=ax.legalize)
    assert not isinstance(rows, str)
    records = [
        {key: "" if value is None else str(value) for key, value in row.items()} for row in rows
    ]
    summary = summarize_generation(records, 1.0, {"degenerate room": 1})
    assert summary.startswith("# Milestone 8")
    assert "**0 plan(s) out of 1 are valid before correction.**" in summary
    assert "{'degenerate room': 1}" in summary


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (Infeasible(farkas_certificate=None, origins=("stub",)), "infaisable"),  # lang-ok: CSV
        (GridNotRecoverable(excess=1, missing=0), "trame"),  # lang-ok: published CSV value
        (InvariantViolation(("stub",)), "invariant_viole"),  # lang-ok: published CSV value
        (GapNeedsTiling(("stub",)), "invariant_viole"),  # lang-ok: published CSV value
    ],
)
def test_a_typed_failure_of_legalize_becomes_its_published_status(
    error: Exception, status: str
) -> None:
    def failing(plan: Plan, context: Context, /, *, tiling: bool, repair_budget: int) -> Plan:
        raise error

    rows = evaluate_generated(RECORD, 1.0, legalize=failing)
    assert not isinstance(rows, str)
    assert {row["status"] for row in rows} == {status}
    assert {row["valid_after"] for row in rows} == {False}
    assert {row["max_displacement_m"] for row in rows} == {""}
    assert {row["relative_displacement"] for row in rows} == {""}


def test_a_record_without_rooms_is_rejected_as_an_empty_union() -> None:
    assert evaluate_generated({**RECORD, "pieces": []}, 1.0, legalize=ax.legalize) == (
        "empty union"
    )
