"""AUDIT 2.2: the six B9 plans in three states (generated, classic legalization,
archlux optimization) x 8 azimuths, measured by one independent reference. Radiance
when its binaries are on PATH (``reference`` column = physical); otherwise the frozen
split-flux closed form, labelled ``closed_form``: no physical claim. Openings: one
window per outline edge (``facade_glazing``), identical for the three states."""

import csv
import json
import sys
from pathlib import Path

import archlux as ax
from archlux.bench.three_states import HEADER, b9_cases, rows
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.radiance import RadianceReference, radiance_available
from archlux.light.reference import ClosedFormReference
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.three_states import compare_three_states

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results") / "b9_three_states.csv"
SURROGATE = AnalyticSurrogate(target_indicator="sDA")
physical = radiance_available()
REFERENCE = RadianceReference() if physical else ClosedFormReference(SplitFluxOracle())
plans = json.loads(Path("results/j9_inputs.json").read_text(encoding="utf-8"))["plans"]
results = compare_three_states(
    SURROGATE, REFERENCE, b9_cases(plans, SURROGATE, legalize=ax.legalize)
)
with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows(results))
print(f"{len(results)} cases, reference: {'Radiance' if physical else 'closed form'}")
