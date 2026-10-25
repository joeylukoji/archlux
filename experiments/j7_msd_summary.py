"""Summary of milestone 7 (B6) from its raw rows (PLAN.md phase 2), the whole page.

Usage: python experiments/j7_msd_summary.py [RAW_CSV] [OUT_MD]. Fallback: try `tiling=True`,
fall back on plain legalize when it refuses, for any reason (the rule behind the published
93.9 %); the strict variant falls back only on an unrecoverable grid. Every number of the
page is computed here from the raw rows: nothing is typed by hand.

Statistical unit: the **dwelling**. The 16 corruptions of one dwelling are not independent,
so next to the row-level Wilson interval each rate gets a bootstrap interval resampling
whole dwellings (``bench.stats.cluster_bootstrap_proportion``, seed 17).
"""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.export.wilson import wilson_interval

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "results/j7_repair_raw.csv")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "results/j7_repair.md")
OLD = {"mode": "fault", "valide_apres": "valid_after", "statut": "status"}  # 2026-09 raw rows
LABELS = {  # raw status (French rows of the published run, then exception names) -> label
    "ok": "certified valid",
    "infaisable": "infeasible (Farkas)",
    "Infeasible": "infeasible (Farkas)",
    "trame": "grid refused",
    "GridNotRecoverable": "grid refused",
    "invariant_viole": "refused by the exact check",
    "InvariantViolation": "refused by the exact check",
    "GapNeedsTiling": "gap needs tiling",
}
GRID_REFUSED = {"trame", "GridNotRecoverable"}
SEED = 17
INTACT_SIDE_M = 0.50
Case = dict[str, dict[str, str]]

cases: dict[tuple[str, str, str], Case] = defaultdict(dict)
with RAW.open(encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        r = {OLD.get(key, key): value for key, value in row.items()}
        cases[r["plan_id"], r["fault"], r["amplitude_m"]][r["pavage"]] = r


def ok(row: dict[str, str]) -> bool:
    return row["valid_after"] == "True"


def fallback(runs: Case) -> dict[str, str]:
    """The row the fallback strategy keeps: tiling first, plain legalize if it refuses."""
    return runs["True"] if runs["True"]["status"] == "ok" else runs["False"]


def strict(runs: Case) -> dict[str, str]:
    """Fall back on plain legalize only when the grid is not recoverable."""
    return runs["False"] if runs["True"]["status"] in GRID_REFUSED else runs["True"]


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.1f} %"


def by_dwelling(rows: list[dict[str, str]], success: list[bool]) -> str:
    interval = cluster_bootstrap_proportion(success, [r["plan_id"] for r in rows], seed=SEED)
    return f"[{100 * interval.low:.1f}, {100 * interval.high:.1f}]"


def times(runs: list[Case]) -> str:
    values = [float(r[p]["time_ms"]) for r in runs for p in r if r[p].get("time_ms")]
    return f"{median(values):.1f} ms" if values else "—"


def rate_table() -> list[str]:
    lines = [
        "| Group | n | `legalize` | `tiling=True` | fallback | Wilson 95 % "
        "| by dwelling 95 % | median t, both modes |",
        "|---|--:|--:|--:|--:|:--:|:--:|--:|",
    ]
    groups: dict[str, list[Case]] = defaultdict(list)
    for (_, fault, amplitude), runs in sorted(cases.items()):
        for group in (f"fault {fault}", "all faults", f"amplitude {amplitude} m"):
            groups[group].append(runs)
    for group, runs in sorted(groups.items()):
        n = len(runs)
        kept = [fallback(r) for r in runs]
        success = [ok(r) for r in kept]
        low, high = wilson_interval(sum(success), n)
        rates = [pct(sum(ok(r[p]) for r in runs), n) for p in ("False", "True")]
        cells = f"{rates[0]} | {rates[1]} | **{pct(sum(success), n)}**"
        wilson = f"[{100 * low:.1f}, {100 * high:.1f}]"
        lines.append(
            f"| {group} | {n} | {cells} | {wilson} | {by_dwelling(kept, success)} | {times(runs)} |"
        )
    return lines


def outcome_table(runs: list[Case]) -> list[str]:
    lines = ["| outcome | `legalize` | `tiling=True` |", "|---|--:|--:|"]
    counts = {
        p: Counter(LABELS.get(r[p]["status"], r[p]["status"]) for r in runs)
        for p in ("False", "True")
    }
    labels = sorted(set(counts["False"]) | set(counts["True"]))
    for label in labels:
        lines.append(f"| {label} | {counts['False'][label]} | {counts['True'][label]} |")
    n = len(runs)
    lines.append(f"| **total** | {n} | {n} |")
    return lines


def validator_lines(runs: list[Case]) -> list[str]:
    rows = [r[p] for r in runs for p in r]
    if "validator_valid" not in rows[0]:
        return [
            "Not recorded: these raw rows predate the independent validator "
            "(`certify.validate_plan`). Re-running `experiments/j7_msd_repair.py` on the "
            "corpus adds `outcome`, `validator_valid` and `evidence` to every row."
        ]
    certified = [r for r in rows if ok(r)]
    refused = sum(r["validator_valid"] != "True" for r in certified)
    evidence = Counter(r["evidence"] for r in certified)
    listing = ", ".join(f"{k}: {v}" for k, v in sorted(evidence.items()))
    return [
        f"{len(certified)} repairs certified valid; the independent validator refuses "
        f"**{refused}** of them. Evidence of the accepted ones: {listing}."
    ]


def intact_lines(runs: list[Case]) -> list[str]:
    kept = [fallback(r) for r in runs]
    if "n_rooms_after" not in kept[0]:
        return [
            "Not recorded: these raw rows have neither the room count nor the smallest "
            "side after repair. Re-running `experiments/j7_msd_repair.py` adds "
            "`n_rooms_after` and `min_side_after`."
        ]
    repaired = [r for r in kept if ok(r)]
    intact = [
        r
        for r in repaired
        if int(r["n_rooms_after"]) == int(r["n_rooms"])
        and float(r["min_side_after"]) >= INTACT_SIDE_M
    ]
    return [
        f"Fallback repairs that kept every room (same count, no side under "
        f"{INTACT_SIDE_M:.2f} m): **{len(intact)} / {len(repaired)}** "
        f"({pct(len(intact), max(len(repaired), 1))}); {pct(len(intact), len(kept))} of all "
        f"{len(kept)} corrupted plans."
    ]


def largest_move(runs: list[Case]) -> str:
    moves = [
        (float(r[p]["max_displacement_m"]), r[p]["plan_id"], r[p]["fault"], r[p]["amplitude_m"], p)
        for r in runs
        for p in r
        if r[p]["max_displacement_m"]
    ]
    d, plan, fault, amplitude, pavage = max(moves)
    mode = "`tiling=True`" if pavage == "True" else "`legalize`"
    return f"{d:.3f} m, dwelling `{plan}`, fault `{fault}` {amplitude} m, {mode}"


def page() -> str:
    runs = [cases[key] for key in sorted(cases)]
    dwellings = {key[0] for key in cases}
    before = sum(r["False"]["valid_before"] == "True" for r in runs)
    n = len(runs)
    success_strict = sum(ok(strict(r)) for r in runs)
    head = [
        "# Milestone 7: repair of corrupted MSD plans",
        "",
        f"MSD corpus, **{len(dwellings)} dwellings**, **{n} corruptions** (cases), root seed "
        f"{SEED}. Every corrupted plan goes through **both** modes ({2 * n} repair "
        "attempts); *fallback* is the applicable strategy: try `tiling=True`, fall back on "
        f"plain `legalize` if it refuses. **{pct(before, n)}** of the corrupted plans are "
        "valid before correction. Generated by `experiments/j7_msd_summary.py` from "
        f"`{RAW.name}`.",
        "",
        "**Statistical unit: the dwelling.** The corruptions of one dwelling are not "
        "independent: the *by dwelling* interval resamples whole dwellings and is the one "
        "to quote; the Wilson interval treats the cases as independent and is too narrow.",
        "",
        *rate_table(),
        "",
        f"Strict fallback (back to plain `legalize` only on an unrecoverable grid): "
        f"**{pct(success_strict, n)}** ({success_strict} / {n}).",
        "",
        "## Outcomes, every attempt counted",
        "",
        *outcome_table(runs),
        "",
        "## Independent validator",
        "",
        *validator_lines(runs),
        "",
        "## Rooms kept",
        "",
        *intact_lines(runs),
        "",
        f"Largest displacement of a certified repair: {largest_move(runs)}.",
        "",
    ]
    return "\n".join(head) + READING


READING = """
## Reading

Without the tiling constraint, the separations of the polytope are **inequalities**: a
plan with a gap is already the closest point to itself, the L1 optimum leaves it as is,
and the exact verification rejects it. Hence the low rate on gaps against overlaps.

`tiling=True` imposes the edge/line incidences of the recovered grid: a gap can no longer
be represented. This does **not** make every program feasible: the outcome table above
lists the infeasible programs (each with a Farkas certificate, valid for the proposed
relative order only), the grids that could not be recovered and the plans the exact check
refused. The fallback rescues part of them with plain `legalize`.

Grid recovery combines two mechanisms without any threshold in metres: the absorption
of **orphan** lines (support < 2), then a **bounded repair** of the partition, which
grows or shrinks a room by one step as long as the cells involved are all missing, or
all in excess. Budget 4: beyond it, the fault is no longer a wrong dimension but an
order inconsistency, and `deduce_grid` refuses.

## Limits

These perturbations are **not** a model of the errors of any particular generator: they
reproduce the fault families reported in the literature, without calibrating their
frequencies.

The repair can **absorb a missing room into its neighbour** (this run uses
`min_width = 0`): closing a gap means enlarging someone. A caller who must preserve the
program room by room passes `repair_budget=0` or a positive `min_width`.
"""

OUT.write_text(page(), encoding="utf-8")
