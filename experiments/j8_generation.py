"""Milestone 8: legalize **actually generated** plans (HouseDiffusion), not corrupted ones.

Rationale, sweeps and summary: :mod:`archlux.bench.generation`.
Usage: j8_generation.py [plans.jsonl] [n_max] [label]
"""

import csv
import json
import sys
from pathlib import Path

import archlux as ax
from archlux.bench.generation import FIELDS, evaluate_generated, summarize_generation
from archlux.data.generated import generated_scale

plans = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/j8_plans.jsonl")
n_max = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
# Output label: the graph conditionings measured must not overwrite each other.
label = sys.argv[3] if len(sys.argv) > 3 else plans.stem
lines = plans.read_text(encoding="utf-8").splitlines()[:n_max]
rows = [json.loads(line) for line in lines if line.strip()]
if not rows:
    raise SystemExit(f"no plan in {plans}")
scale = generated_scale(rows)
print(f"{len(rows)} generated plans, scale {scale:.4f} m/unit")

Path("results").mkdir(exist_ok=True)
output = Path(f"results/j8_{label}_raw.csv")
rejections: dict[str, int] = {}
with output.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    for plan_json in rows:
        result = evaluate_generated(plan_json, scale, legalize=ax.legalize)
        if isinstance(result, str):
            rejections[result] = rejections.get(result, 0) + 1
            continue
        writer.writerows(result)
print("raw rows written:", output)
with output.open(encoding="utf-8") as stream:
    records = list(csv.DictReader(stream))
summary = Path(f"results/j8_{label}.md")
summary.write_text(summarize_generation(records, scale, rejections), encoding="utf-8")
print("summary written:", summary)
if rejections:
    print("rejections:", rejections)
