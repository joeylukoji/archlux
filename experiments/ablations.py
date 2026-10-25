"""Ablations of spec 1.9 on one fixed input set: 2x2 synthetic plans of j2, one fault at
0.25 m, N_INITS corruption seeds each, one azimuth per source. Same inputs for every
configuration. Usage: ablations.py [OUT_DIR] [N_PLANS] [N_INITS]. Reference = frozen
SplitFluxOracle, not Radiance. See archlux.bench.ablation."""

import sys
from pathlib import Path

import archlux as ax
from archlux.bench import ablation as ab
from archlux.bench import repro
from archlux.data.synthetic import generate_corpus, two_room_vectors
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 90
INITS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
SEED = 17
model, reference = AnalyticSurrogate(), SplitFluxOracle()


def context(plan: ax.Plan, orientation: ax.Orientation) -> ax.Context:
    cut = next(r.x + r.w for r in plan.rooms if r.id == "sw")
    wall = ax.Wall(id="lb", a=(cut, 0.0), b=(cut, 9.0), load_bearing=True)
    kinds = sorted({r.type for r in plan.rooms})
    minima = tuple((t, 0.8 * min(r.w * r.h for r in plan.rooms if r.type == t)) for t in kinds)
    regulation = ax.Regulation(minima, 1.0)
    return ax.Context(ax.Structure((wall,)), orientation, regulation, outline=plan.outline)


calibration = list(zip(*two_room_vectors(200, seed=SEED + 1), strict=True))  # disjoint
q_hat = ab.calibrate_q(model, reference, calibration)
plans = dict(sorted(generate_corpus(N, seed=SEED).items()))
cases = ab.make_cases(plans, context, seed=SEED, n_inits=INITS)
configs = ab.configurations(model, reference, q_hat, budgets=(0.5, 1.0, 2.0, 3.0))
kwargs = {"legalize_trace": ax.legalize_trace, "model": model, "reference": reference}
rows = ab.run_ablations(cases, configs, **kwargs)
ab.write_ablation_rows(OUT / "ablations_raw.csv", rows)
head = f"# Ablations\n\n{len(plans)} source plans x {INITS} initialisations, seed {SEED}, "
head += f"q_hat {q_hat:.3f}. Gains are paired against `repair`. Raw rows: `ablations_raw.csv`.\n\n"
(OUT / "ablations.md").write_text(head + ab.summarize_ablations(rows, seed=SEED), encoding="utf-8")
params = {"n_plans": N, "n_inits": INITS, "amplitude_m": 0.25, "q_hat": q_hat, "alpha": 0.10}
params |= {"budgets_m": (0.5, 1.0, 2.0, 3.0), "configs": list(configs)}
outputs = [OUT / "ablations_raw.csv", OUT / "ablations.md"]
command = f"python experiments/ablations.py {OUT} {N} {INITS}"
run = repro.record(seed=SEED, command=command, parameters=params, outputs=outputs)
repro.write_record(OUT / "ablations_manifest.json", run)
