"""Pooled summary of milestone 8 (B8) over its three sets, every setting stated explicitly.

Usage: python experiments/j8_summary.py [RESULTS_DIR]. Reads ``j8_etoile_raw.csv``,
``j8_plausible_raw.csv`` and ``j8_divers_raw.csv`` (written by ``j8_generation.py``) and
writes ``j8_pooled.md``. Every rate names its ``mode``, ``budget`` and ``min_width``: the
hand-written synthesis ``j8_generation.md`` mixed two width settings without saying so.

Statistical unit: the **generated plan**. The *etoile* and *plausible* sets sample the same
320 programmes slot by slot (``plan_id``), so they are paired, not independent: the pooled
interval resamples whole slots (``bench.stats.cluster_bootstrap_proportion``, seed 17),
an *etoile* and a *plausible* plan of one slot staying together.
"""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.export.wilson import wilson_interval

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
SETS = ("etoile", "plausible", "divers")
SEED = 17
LABELS = {
    "ok": "certified valid",
    "infaisable": "infeasible (Farkas)",
    "Infeasible": "infeasible (Farkas)",
    "trame": "grid refused",
    "GridNotRecoverable": "grid refused",
    "invariant_viole": "refused by the exact check",
    "InvariantViolation": "refused by the exact check",
}
Row = dict[str, str]


def load() -> list[Row]:
    rows = []
    for name in SETS:
        with (ROOT / f"j8_{name}_raw.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                slot = row["plan_id"] if name != "divers" else f"divers/{row['plan_id']}"
                rows.append({**row, "set": name, "slot": slot})
    return rows


def ok(row: Row) -> bool:
    return row["valid_after"] == "True"


def setting(row: Row) -> tuple[str, str, str]:
    return row["mode"], row["budget"] or "—", row["min_width"]


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.1f} %" if n else "—"


def interval(rows: list[Row]) -> str:
    success = [ok(r) for r in rows]
    low, high = wilson_interval(sum(success), len(rows))
    boot = cluster_bootstrap_proportion(success, [r["slot"] for r in rows], seed=SEED)
    wilson = f"[{100 * low:.1f}, {100 * high:.1f}]"
    return f"{wilson} | [{100 * boot.low:.1f}, {100 * boot.high:.1f}]"


def rate_table(rows: list[Row]) -> list[str]:
    lines = [
        "| mode | budget | `min_width` | n | certified valid | Wilson 95 % "
        "| by slot 95 % | etoile | plausible | divers |",
        "|---|--:|--:|--:|--:|:--:|:--:|--:|--:|--:|",
    ]
    groups: dict[tuple[str, str, str], list[Row]] = defaultdict(list)
    for row in rows:
        groups[setting(row)].append(row)
    order = sorted(groups, key=lambda s: (s[0], int(s[1]) if s[1].isdigit() else -1, s[2]))
    for key in order:
        group = groups[key]
        k = sum(ok(r) for r in group)
        per_set = [[r for r in group if r["set"] == name] for name in SETS]
        cells = " | ".join(pct(sum(ok(r) for r in s), len(s)) for s in per_set)
        mode, budget, width = key
        lines.append(
            f"| `{mode}` | {budget} | {width} m | {len(group)} | **{k}** ({pct(k, len(group))}) "
            f"| {interval(group)} | {cells} |"
        )
    return lines


def outcome_table(rows: list[Row], budget: str) -> list[str]:
    chosen = [r for r in rows if r["mode"] == "pavage" and r["budget"] == budget]
    widths = sorted({r["min_width"] for r in chosen})
    counts = {
        w: Counter(LABELS.get(r["status"], r["status"]) for r in chosen if r["min_width"] == w)
        for w in widths
    }
    labels = sorted({label for c in counts.values() for label in c})
    lines = [
        "| outcome | " + " | ".join(f"`min_width` {w} m" for w in widths) + " |",
        "|---|" + "--:|" * len(widths),
    ]
    for label in labels:
        lines.append(f"| {label} | " + " | ".join(str(counts[w][label]) for w in widths) + " |")
    totals = " | ".join(str(sum(counts[w].values())) for w in widths)
    lines.append(f"| **total** | {totals} |")
    return lines


def size_table(rows: list[Row], width: str) -> list[str]:
    chosen = [
        r for r in rows if r["mode"] == "pavage" and r["budget"] == "16" and r["min_width"] == width
    ]
    sizes = sorted({int(r["n_rooms"]) for r in chosen})
    lines = [
        f"Budget 16, `min_width = {width} m`:",
        "",
        "| rooms | etoile | plausible | divers | pooled n | pooled | intact (no side < 0.50 m) |",
        "|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for size in sizes:
        group = [r for r in chosen if int(r["n_rooms"]) == size]
        per_set = [[r for r in group if r["set"] == name] for name in SETS]
        cells = " | ".join(pct(sum(ok(r) for r in s), len(s)) for s in per_set)
        intact = sum(r.get("intact") == "True" for r in group)
        k = sum(ok(r) for r in group)
        pooled = f"{len(group)} | {pct(k, len(group))} | {pct(intact, len(group))}"
        lines.append(f"| {size} | {cells} | {pooled} |")
    return lines


def page() -> str:
    rows = load()
    n_plans = {name: len({r["plan_id"] for r in rows if r["set"] == name}) for name in SETS}
    total = sum(n_plans.values())
    sets = ", ".join(f"{name} {n}" for name, n in n_plans.items())
    return "\n".join(
        [
            "# Milestone 8: pooled repair rates, every setting stated",
            "",
            f"{total} generated plans ({sets}). Generated by `experiments/j8_summary.py` from "
            "the three `j8_*_raw.csv` files. **Statistical unit: the generated plan**; "
            "*etoile* and *plausible* share their 320 programme slots and are paired, so "
            "the *by slot* interval (bootstrap over slots) is the one to quote for pooled "
            "rates.",
            "",
            "## Certified valid, by setting",
            "",
            *rate_table(rows),
            "",
            "## Outcomes at budget 16, by width floor",
            "",
            "Every attempt is counted; nothing crashed.",
            "",
            *outcome_table(rows, "16"),
            "",
            "## By programme size",
            "",
            *size_table(rows, "0.00"),
            "",
            *size_table(rows, "0.50"),
            "",
        ]
    )


(ROOT / "j8_pooled.md").write_text(page(), encoding="utf-8")
