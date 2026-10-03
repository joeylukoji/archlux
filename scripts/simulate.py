"""Simulate the corpus: labels from the frozen split-flux oracle, not a ground truth."""

from __future__ import annotations

import csv
import time
from pathlib import Path

from archlux.data.synthetic import generate_corpus
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.tokens import plan_to_vector
from archlux.types import Orientation

out = Path("results/j4_simulations.csv")
out.parent.mkdir(exist_ok=True)
sim, corpus = SplitFluxOracle(), generate_corpus(90, seed=17)
fields = (
    "id",
    "orientation",
    "score",
    "engine",
    "weather_file",
    "sky_model",
    "duration_s",
)
with out.open("w", newline="", encoding="utf-8") as handle:
    w = csv.DictWriter(handle, fieldnames=fields)
    w.writeheader()
    for identifier, plan in corpus.items():
        start = time.perf_counter()
        score = sim.evaluate(plan_to_vector(plan), Orientation(deg=0.0))
        w.writerow(
            {
                "id": identifier,
                "orientation": 0.0,
                "score": score,
                "engine": "synthetic",
                "weather_file": "",
                "sky_model": "closed_form",
                "duration_s": f"{time.perf_counter() - start:.6f}",
            }
        )
print("rows", 90)
