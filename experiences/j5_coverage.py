"""Milestone 5 coverage over 20 calibrations (PLAN.md phase 2): held-out ("exchangeable")
and Frank-Wolfe-chosen ("selected") plans, Clopper-Pearson intervals, width vs spread."""

import csv
import sys
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.data.synthese import TWO_ROOM_OUTLINE, two_room_plan, two_room_vectors
from archlux.geom.polytope import decision_vector
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.light.simulateur import SplitFluxOracle
from archlux.seeds import derive
from archlux.uq.conforme import CalibrateurConforme
from archlux.uq.fiabilite import measure_coverage

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "resultats") / "j5_coverage.csv"
model, oracle = SubstitutAnalytique(), SplitFluxOracle()


def columns(xs: tuple, orientations: tuple) -> list[np.ndarray]:
    fs = (model.evaluer, oracle.evaluer, model.incertitude)  # the order of cal.ajuster
    return [np.array([f(x, o) for x, o in zip(xs, orientations, strict=True)]) for f in fs]


def chosen(xs: tuple, orientations: tuple, q: float) -> tuple:
    """Start from each held-out plan and let Frank-Wolfe choose where it goes."""
    fw, ref = Daylight(model, q_chapeau=q), ax.Referentiel((), 1.0)
    ctx = [ax.Contexte(ax.Structure(()), o, TWO_ROOM_OUTLINE, ref) for o in orientations]
    plans = (ax.legalize(two_room_plan(x), c, objective=fw) for x, c in zip(xs, ctx, strict=True))
    return tuple(decision_vector(plan) for plan in plans)


with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("run", "regime", "n", "coverage", "low", "high", "mean_width", "target_std"))
    for run in range(20):  # named sub-seeds: no stream shared between runs or samples
        cal = CalibrateurConforme()
        cal.ajuster(*columns(*two_room_vectors(220, seed=derive(17, f"cal/{run}"))), alpha=0.10)
        starts, orientations = two_room_vectors(80, seed=derive(17, f"starts/{run}"))
        selected = (chosen(starts, orientations, cal.q), orientations)
        exchangeable = two_room_vectors(280, seed=derive(17, f"test/{run}"))
        for regime, sample in (("exchangeable", exchangeable), ("selected", selected)):
            r = measure_coverage(cal, *columns(*sample), regime=regime)
            stats = (r.coverage, r.coverage_low, r.coverage_high, r.mean_width, r.target_std)
            writer.writerow((run, regime, r.n, *(f"{v:.4f}" for v in stats)))
