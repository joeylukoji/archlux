"""Label the corpus with the frozen split-flux oracle: a closed form, not a ground truth.

Every row says so: ``kind = closed_form``. ``--radiance`` labels with
:class:`archlux.light.radiance.RadianceReference` instead (``kind = physical``); it needs
``oconv``, ``rtrace`` and ``gensky`` on ``PATH`` and plans **with openings**, so on the
synthetic corpus (no openings) every row is written ``not_measured`` with its reason,
never a number.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from archlux.data.synthetic import generate_corpus
from archlux.light.protocol import Glazing
from archlux.light.radiance import RadianceReference
from archlux.light.reference import ClosedFormReference, ReferenceUnavailable
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.tokens import plan_to_vector
from archlux.types import Orientation

physical = "--radiance" in sys.argv[1:]
reference = RadianceReference() if physical else ClosedFormReference(SplitFluxOracle())
out = Path("results/j4_simulations_radiance.csv" if physical else "results/j4_simulations.csv")
out.parent.mkdir(exist_ok=True)
corpus = generate_corpus(90, seed=17)
fields = ("id", "orientation", "score", "unit", "kind", "engine", "parameters", "duration_s")
with out.open("w", newline="", encoding="utf-8") as handle:
    w = csv.DictWriter(handle, fieldnames=fields)
    w.writeheader()
    for identifier, plan in corpus.items():
        start = time.perf_counter()
        glazing = Glazing(walls=plan.walls, openings=plan.openings)
        row = {"id": identifier, "orientation": 0.0, "kind": reference.kind}
        try:
            m = reference.measure(plan_to_vector(plan), Orientation(deg=0.0), glazing=glazing)
            row |= {"score": m.value, "unit": m.unit, "engine": m.engine,
                    "parameters": ";".join(f"{k}={v}" for k, v in m.parameters)}  # fmt: skip
        except ReferenceUnavailable as missing:
            row |= {"score": "not_measured", "unit": reference.unit, "engine": missing.detail}
        row["duration_s"] = f"{time.perf_counter() - start:.6f}"
        w.writerow(row)
print("rows", len(corpus), "kind", reference.kind)
