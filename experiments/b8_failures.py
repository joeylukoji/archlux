"""AUDIT 2.3: B8 broken down by failure class, conditioning and program size, from the
raw rows of ``j8_*_raw.csv`` (tiling, repair budget 16, min width 0.50 m). A repair
moving more than 25 % of the plan's side counts as a strong deformation."""

import csv
import sys
from pathlib import Path

from archlux.bench.failures import CLASSES, failure_table

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results") / "b8_failures.md"
rows = [
    {**row, "set": name}
    for name in ("etoile", "plausible", "divers")
    for row in csv.DictReader(Path(f"results/j8_{name}_raw.csv").read_text("utf-8").splitlines())
    if (row["mode"], row["budget"], row["min_width"]) == ("pavage", "16", "0.50")
]
lines = ["# B8 failures by class (tiling, repair budget 16, min width 0.50 m)", ""]
for by in ("set", "graph", "n_rooms"):
    lines += [f"## By {by}", "", f"| {by} | n | {' | '.join(CLASSES)} | repaired [Wilson 95 %] |"]
    lines.append("|---" * (len(CLASSES) + 3) + "|")
    for group, n, counts, (low, high) in failure_table(rows, by=by):
        share = (counts["repaired"] + counts["repaired_strong_deformation"]) / n
        cells = " | ".join(str(counts[c]) for c in CLASSES)
        ci = f"{100 * share:.1f} % [{100 * low:.1f} ; {100 * high:.1f}]"
        lines.append(f"| {group} | {n} | {cells} | {ci} |")
    lines.append("")
lines += [
    "Legalize alone (no tiling) repairs none: every generated plan leaves a gap, a",
    "stationary point of the L1 optimum; the current code reports it as GapNeedsTiling",
    "(the raw rows, older, label it invariant_viole). Visual examples per class:",
    "`results/visuals/<set>/{repaired,proven-infeasible,unrecoverable-grid}/`.",
]
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
