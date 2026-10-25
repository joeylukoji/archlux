"""Ablations of spec 1.9 on one fixed input set: 2x2 synthetic plans of j2, one fault at
0.25 m, N_INITS corruption seeds each, one azimuth per source. Same inputs for every
configuration. Usage: ablations.py [OUT_DIR] [N_PLANS] [N_INITS]. Reference = frozen
SplitFluxOracle, not Radiance. See archlux.bench.ablation."""

import sys
from pathlib import Path

import archlux as ax
from archlux.bench import ablation as ab
from archlux.bench import repro
from archlux.bench import room_selection as rs
from archlux.bench.ensemble import fit_dense_ensemble
from archlux.data.synthetic import generate_corpus, two_room_vectors
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.objective import Daylight
from archlux.light.split_flux import SplitFluxOracle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 90
INITS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
SEED, K, POOL, CAL = 17, 5, 200, 100
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
configs = ab.configurations(
    model, reference, q_hat, budgets=(0.5, 1.0, 2.0, 3.0), gradient_free=True
)
kwargs = {"legalize_trace": ax.legalize_trace, "model": model, "reference": reference}
rows = ab.run_ablations(cases, configs, **kwargs)
ab.write_ablation_rows(OUT / "ablations_raw.csv", rows)

# Non-constant sigma_hat: a bootstrap ensemble of K DenseSurrogate, trained on POOL
# four-room plans and calibrated on CAL others, both disjoint from the ablation sources.
pool = rs.four_room_variants(POOL, seed=SEED + 2, n_azimuths=1, prefix="pool")
truths = [reference.evaluate(v.x, v.orientation) for v in pool]
ensemble = fit_dense_ensemble(
    [v.x for v in pool], truths, [v.orientation for v in pool], k=K, seed=SEED
)
cal = rs.four_room_variants(CAL, seed=SEED + 3, n_azimuths=1, prefix="cal")
q_ens = ab.calibrate_q(ensemble, reference, [(v.x, v.orientation) for v in cal])
ens_configs = {
    "repair": configs["repair"],
    "fw_ensemble": {"tiling": True, "objective": Daylight(ensemble, q_hat=q_ens)},
    "fw_ensemble_no_penalty": {
        "tiling": True,
        "objective": Daylight(ensemble, q_hat=q_ens, pessimistic=False),
    },
}
ens_kwargs = {**kwargs, "model": ensemble}
ens_rows = ab.run_ablations(cases, ens_configs, **ens_kwargs)
ab.write_ablation_rows(OUT / "ablations_ensemble_raw.csv", ens_rows)

head = f"# Ablations\n\n{len(plans)} source plans x {INITS} initialisations, seed {SEED}, "
head += f"q_hat {q_hat:.3f}. Gains are paired against `repair`. Raw rows: `ablations_raw.csv`.\n\n"
ens = f"\n## Uncertainty penalty with a varying sigma_hat\n\nSame {len(cases)} cases. "
ens += f"Surrogate = bootstrap ensemble of {K} `DenseSurrogate` (trained on {POOL} other "
ens += f"four-room plans, q_hat {q_ens:.3f} calibrated on {CAL} more), sigma_hat = spread "
ens += "of the members. Surrogate gains are the ensemble's, paired against `repair`. Raw "
ens += "rows: `ablations_ensemble_raw.csv`.\n\n"
body = ab.summarize_ablations(rows, seed=SEED) + ens + ab.summarize_ablations(ens_rows, seed=SEED)
(OUT / "ablations.md").write_text(head + body, encoding="utf-8")
params = {"n_plans": N, "n_inits": INITS, "amplitude_m": 0.25, "q_hat": q_hat, "alpha": 0.10}
params |= {"budgets_m": (0.5, 1.0, 2.0, 3.0), "configs": list(configs)}
params |= {"ensemble_k": K, "ensemble_pool": POOL, "ensemble_calibration": CAL, "q_ensemble": q_ens}
outputs = [OUT / "ablations_raw.csv", OUT / "ablations_ensemble_raw.csv", OUT / "ablations.md"]
command = f"python experiments/ablations.py {OUT} {N} {INITS}"
run = repro.record(seed=SEED, command=command, parameters=params, outputs=outputs)
repro.write_record(OUT / "ablations_manifest.json", run)
