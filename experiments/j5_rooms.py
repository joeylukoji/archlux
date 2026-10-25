"""Coverage by room type and with a non-constant sigma_hat (paper B4, second pass).

Two protocols on typed four-room plans (12 x 9 m, continuous cuts) x 4 azimuths, split
by source plan, fresh split per repetition, reference = frozen SplitFluxOracle (closed
form, not a simulation):

1. per room: interval on every room, analytic surrogate rescaled per room, coverage by
   room type and by orientation (archlux.bench.room_selection);
2. per plan, with a bootstrap ensemble of 5 DenseSurrogate trained on a disjoint pool of
   sources: the first sigma_hat of the bench that varies (archlux.bench.ensemble).

Usage: j5_rooms.py [OUT_DIR] [N_SOURCES] [REPETITIONS]. Raw rows are the result."""

import sys
from pathlib import Path

import archlux as ax
from archlux.bench import repro
from archlux.bench import room_selection as rs
from archlux.bench import selection as sel
from archlux.bench.ensemble import fit_dense_ensemble
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 400
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 10
SEED, ALPHA, K, POOL = 17, 0.10, 5, 200
oracle = SplitFluxOracle()
variants = rs.four_room_variants(N, seed=SEED)
policy = sel.legalize_policy(
    ax.legalize, rs.four_room_plan, rs.FOUR_ROOM_OUTLINE, ax.Regulation((), 1.0)
)

rooms, room_info = rs.run_room_protocol(
    variants,
    base=AnalyticSurrogate(),
    oracle=oracle,
    make_policy=policy,
    seed=SEED,
    repetitions=REPS,
    alpha=ALPHA,
)
rs.write_room_rows(OUT / "j5_rooms_raw.csv", rooms)

pool = rs.four_room_variants(POOL, seed=SEED + 1, n_azimuths=1, prefix="pool")
ensemble = fit_dense_ensemble(
    [v.x for v in pool],
    [oracle.evaluate(v.x, v.orientation) for v in pool],
    [v.orientation for v in pool],
    k=K,
    seed=SEED,
)
plans, plan_info = sel.run_selection_protocol(
    variants,
    base=ensemble,
    oracle=oracle,
    make_policy=policy,
    seed=SEED,
    repetitions=REPS,
    alpha=ALPHA,
)
sel.write_rows(OUT / "j5_ensemble_raw.csv", plans)

head = f"# Coverage by room type, and with a varying sigma_hat\n\n{N} typed four-room source "
head += f"plans x 4 azimuths, {REPS} repetitions, alpha = {ALPHA}, seed {SEED}. Reference: "
head += "frozen `SplitFluxOracle` (closed form, **not** a simulation). Synthetic plans only.\n\n"
part1 = "## 1. Per room (analytic surrogate rescaled per room, constant sigma_hat)\n\n"
part1 += "Raw rows: `j5_rooms_raw.csv`. Unit = one room; clusters = repetition x source.\n\n"
part1 += sel.to_markdown(
    sel.summarize(rooms, seed=SEED, keys=("room_type", "sector", "level")), room_info, alpha=ALPHA
)
part2 = f"\n## 2. Per plan, bootstrap ensemble of {K} DenseSurrogate (varying sigma_hat)\n\n"
part2 += f"Members trained on {POOL} other source plans (`pool-*`, one azimuth each), never in "
part2 += "any split. Raw rows: `j5_ensemble_raw.csv`.\n\n"
part2 += sel.to_markdown(sel.summarize(plans, seed=SEED), plan_info, alpha=ALPHA)
(OUT / "j5_rooms.md").write_text(head + part1 + part2, encoding="utf-8")

params = {"n_sources": N, "azimuths": 4, "repetitions": REPS, "alpha": ALPHA, "policy": "legalize"}
params |= {"fractions": (0.4, 0.1, 0.25, 0.25), "ensemble_k": K, "ensemble_pool": POOL}
outputs = [OUT / "j5_rooms_raw.csv", OUT / "j5_ensemble_raw.csv", OUT / "j5_rooms.md"]
command = f"python experiments/j5_rooms.py {OUT} {N} {REPS}"
run = repro.record(seed=SEED, command=command, parameters=params, outputs=outputs)
records = {"rooms": room_info.records, "ensemble": plan_info.records}
repro.write_record(OUT / "j5_rooms_manifest.json", {**run, "runs": records})
