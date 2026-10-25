"""Surrogate reliability beyond the j4 checkpoint (spec 1.3 / 1.5): same network, seed 17.

Reference = the frozen split-flux oracle, labelled ``closed_form``: nothing here is
physical. Sign agreement per 45-degree sector and amplitude, on held-out plans and on the
plans Frank-Wolfe returned; predicted vs realised gain per step; before/after gains with
the out-of-distribution flag.
"""

import csv
import sys
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.light.base import DenseSurrogate
from archlux.light.evaluation import EvaluationCase, compare_before_after
from archlux.light.ood import fit_envelope
from archlux.light.reference import ClosedFormReference
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.tokens import plan_to_vector
from archlux.light.trust import gradient_reliability, step_gain_audit

SEED, OUT = 17, Path(sys.argv[1] if len(sys.argv) > 1 else "results")
ORACLE, rng = SplitFluxOracle(), np.random.default_rng(SEED)
OUTLINE = ((0.0, 0.0), (12.0, 0.0), (12.0, 4.5), (0.0, 4.5))


def draw(n):
    xs = [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in rng.uniform(4, 8, n)]
    return xs, [ax.Orientation(float(d)) for d in rng.uniform(0.0, 360.0, n)]


def optimize(k, x, deg):
    """L1 plan, Frank-Wolfe plan and step audit of one held-out plan at a sector azimuth."""
    rooms = tuple(ax.Room(id=f"r{i}", type="bedroom", x=x[4 * i], y=0.0, w=x[4 * i + 2], h=4.5)
                  for i in (0, 1))  # fmt: skip
    plan, ori = ax.Plan(rooms, (), (), OUTLINE), ax.Orientation(deg)
    ctx = ax.Context(structure=ax.Structure(()), orientation=ori, outline=OUTLINE,
                     regulation=ax.Regulation((), 1.0))  # fmt: skip
    out, trace = ax.legalize_trace(plan, ctx, objective=NET)
    steps = step_gain_audit(NET, ORACLE, [it.x for it in trace.iterations], ori)
    before = plan_to_vector(ax.legalize(plan, ctx))
    return (f"t{k}", before, plan_to_vector(out), ori, None), steps


(train_x, train_o), (test_x, test_o), calib = draw(36), draw(80), draw(40)  # j4 draws first
NET = DenseSurrogate()
train_y = np.array([ORACLE.evaluate(x, o) for x, o in zip(train_x, train_o, strict=True)])
NET.fit(tuple(train_x), train_y, tuple(train_o), seed=SEED, epochs=40, lr=0.12)
envelope = fit_envelope(train_x, train_o, calibration=calib)
held = [EvaluationCase(f"t{k}", x, o, None, "two_rooms", "none")
        for k, (x, o) in enumerate(zip(test_x, test_o, strict=True))]  # fmt: skip
runs = [optimize(k, test_x[k], test_o[k].deg // 45 * 45) for k in range(16)]
pairs, audits = [p for p, _ in runs], [s for _, steps in runs for s in steps]
moved = [EvaluationCase(p[0], p[2], p[3], None, "two_rooms", "none") for p in pairs]
with (OUT / "j4_reliability.csv").open("w", newline="", encoding="utf-8") as handle:
    w = csv.writer(handle, lineterminator="\n")
    w.writerow(("plans", "grouping", "group", "step_m", "n_points", "n_coords",
                "sign_agreement", "mean_cosine", "passed"))  # fmt: skip
    for name, cases in (("held_out", held), ("optimized", moved)):
        for r in gradient_reliability(NET, ORACLE, cases, sector_deg=45.0):
            a = r.agreement
            if r.grouping in ("all", "azimuth"):
                sign, cosine = f"{a.sign_agreement:.4f}", f"{a.mean_cosine:.4f}"
                w.writerow((name, r.grouping, r.group, a.step, a.n_points, a.n_coordinates,
                            sign, cosine, r.passed))  # fmt: skip
    agree = np.mean([s.sign_agrees for s in audits])
    w.writerow(("fw_steps", "all", "all", "", len(audits), "", f"{agree:.4f}", "", ""))
with (OUT / "j4_before_after.csv").open("w", newline="", encoding="utf-8") as handle:
    w = csv.writer(handle, lineterminator="\n")
    w.writerow(("id", "azimuth", "predicted_gain_pct", "reference_gain_pct", "gap_pct",
                "displacement_l1_m", "status", "ood"))  # fmt: skip
    rows = compare_before_after(NET, ClosedFormReference(ORACLE), pairs)
    for p, r in zip(pairs, rows, strict=True):
        w.writerow((r.id, p[3].deg, f"{r.predicted_gain_pct:.4f}", f"{r.reference_gain_pct:.4f}",
                    f"{r.gap_pct:.4f}", f"{r.displacement_l1:.4f}", r.status,
                    envelope.check(p[2], p[3]).uncertain))  # fmt: skip
