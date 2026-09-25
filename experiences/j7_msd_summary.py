"""Summary table of milestone 7 from its raw rows (PLAN.md phase 2).

Usage: python experiences/j7_msd_summary.py [RAW_CSV] [OUT_MD]. Fallback: try pavage,
fall back on plain legalize when it refuses, for any reason (the rule behind the published
93.9 %; falling back only on an unrecoverable grid gives 93.5 %). Wilson 95 % intervals.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

from archlux.export.wilson import intervalle_wilson

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "resultats/j7_repair_raw.csv")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "resultats/j7_repair.md")
cases: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
with RAW.open(encoding="utf-8") as handle:
    for r in csv.DictReader(handle):
        cases[r["plan_id"], r["fault"], r["amplitude_m"]][r["pavage"]] = r


def ok(row: dict[str, str]) -> bool:
    return row["valid_after"] == "True"


lines = [
    "| Group | n | `legalize` | `pavage=True` | fallback | Wilson 95 % |",
    "|---|--:|--:|--:|--:|:--:|",
]
groups: dict[str, list[dict[str, dict[str, str]]]] = defaultdict(list)
for (_, fault, amplitude), runs in sorted(cases.items()):
    for group in (f"fault {fault}", "all faults", f"amplitude {amplitude} m"):
        groups[group].append(runs)
for group, runs in sorted(groups.items()):
    n = len(runs)
    fallback = sum(ok(r["True"] if r["True"]["status"] == "ok" else r["False"]) for r in runs)
    low, high = intervalle_wilson(fallback, n)
    rates = [100 * sum(ok(r[p]) for r in runs) / n for p in ("False", "True")]
    cells = f"{rates[0]:.1f} % | {rates[1]:.1f} % | **{100 * fallback / n:.1f} %**"
    lines.append(f"| {group} | {n} | {cells} | [{100 * low:.1f}, {100 * high:.1f}] |")
OUT.write_text(
    "# Milestone 7: repair of corrupted MSD plans\n\n" + "\n".join(lines) + "\n", encoding="utf-8"
)
