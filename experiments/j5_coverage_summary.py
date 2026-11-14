"""AUDIT 2.4: summary of ``j5_coverage_<n>.csv`` (default 200 calibration draws): mean
coverage with a 95 % interval over draws, draws inside the a-priori band [86 ; 94] %,
width in target standard deviations, paired Wilcoxon exchangeable vs selected."""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from archlux.uq.reliability import ACCEPTANCE_BAND

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 200
rows = list(csv.DictReader((OUT / f"j5_coverage_{RUNS}.csv").read_text("utf-8").splitlines()))
low, high = ACCEPTANCE_BAND
lines = [f"# Conformal coverage over {RUNS} calibration draws (alpha = 0.10)", ""]
lines += ["| regime | draws | mean coverage [95 % CI] | in band | width / sd(target) |"]
lines += ["|---|--:|:--:|--:|--:|"]
cover = {}
for regime in ("exchangeable", "selected"):
    sub = [r for r in rows if r["regime"] == regime]
    c = np.array([float(r["coverage"]) for r in sub])
    w = np.mean([float(r["mean_width"]) / float(r["target_std"]) for r in sub])
    half = 1.96 * c.std(ddof=1) / np.sqrt(c.size)
    inside = int(((c >= low) & (c <= high)).sum())
    ci = f"{100 * c.mean():.1f} % [{100 * (c.mean() - half):.1f} ; {100 * (c.mean() + half):.1f}]"
    lines.append(f"| {regime} | {c.size} | {ci} | {inside}/{c.size} | {w:.2f} |")
    cover[regime] = c
diff = cover["exchangeable"] - cover["selected"]
p = wilcoxon(cover["exchangeable"], cover["selected"]).pvalue
lines += ["", f"Paired difference: {100 * diff.mean():.2f} points, Wilcoxon p = {p:.1e}."]
(OUT / f"j5_coverage_{RUNS}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
