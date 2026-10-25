"""Coverage before and after selection (paper B4 revisited): two-room source plans x 4
azimuths, split by source plan, passive vs frozen-policy calibration, fresh split per
repetition. Usage: j5_selection.py [OUT_DIR] [N_SOURCES] [REPETITIONS].
See archlux.bench.selection; the raw rows are the published result."""

import sys
from pathlib import Path

import archlux as ax
from archlux.bench import repro
from archlux.bench import selection as sel
from archlux.data.synthetic import TWO_ROOM_OUTLINE, two_room_plan
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 400
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 10
SEED, ALPHA = 17, 0.10
policy = sel.legalize_policy(ax.legalize, two_room_plan, TWO_ROOM_OUTLINE, ax.Regulation((), 1.0))
rows, info = sel.run_selection_protocol(
    sel.two_room_variants(N, seed=SEED),
    base=AnalyticSurrogate(),
    oracle=SplitFluxOracle(),
    make_policy=policy,
    seed=SEED,
    repetitions=REPS,
    alpha=ALPHA,
)
sel.write_rows(OUT / "j5_selection_raw.csv", rows)
head = f"# Coverage before and after selection\n\n{N} source plans x 4 azimuths, "
head += f"{REPS} repetitions, alpha = {ALPHA}, seed {SEED}. Raw rows: `j5_selection_raw.csv`.\n\n"
body = sel.to_markdown(sel.summarize(rows, seed=SEED), info, alpha=ALPHA)
(OUT / "j5_selection.md").write_text(head + body, encoding="utf-8")
params = {"n_sources": N, "azimuths": 4, "repetitions": REPS, "alpha": ALPHA, "policy": "legalize"}
params |= {"fractions": (0.4, 0.1, 0.25, 0.25), "surrogate": "AnalyticSurrogate+affine"}
outputs = [OUT / "j5_selection_raw.csv", OUT / "j5_selection.md"]
command = f"python experiments/j5_selection.py {OUT} {N} {REPS}"
run = repro.record(seed=SEED, command=command, parameters=params, outputs=outputs)
repro.write_record(OUT / "j5_selection_manifest.json", {**run, "runs": info.records})
