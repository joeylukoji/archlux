"""B7 errors by orientation, room type and glazing, against the frozen closed form.

The paper's B7 compares the surrogate with Swiss Dwellings simulations (j7_sd_labels.py,
j7_sd_per_room.py); that corpus is not redistributed and is not in this repository. This
script runs the **same breakdown** on what is available everywhere: typed four-room
synthetic plans x 4 azimuths, split by source plan (train 50 % / test 50 %), reference =
frozen SplitFluxOracle (closed form, **not** a simulation). It measures how well each
surrogate reproduces that oracle, never daylight.

Glazing cannot be broken down here: the synthetic plans carry no openings and the oracle
ignores glazing (its WWR is a constant). That breakdown needs the Swiss Dwellings run.

Usage: j7_sd_groups.py [OUT_DIR] [N_SOURCES]."""

import sys
from pathlib import Path

import numpy as np

from archlux.bench import breakdown as bd
from archlux.bench import repro
from archlux.bench import room_selection as rs
from archlux.bench.ensemble import fit_dense_ensemble
from archlux.bench.selection import fit_affine
from archlux.data.provenance import check_no_group_leakage, split_by_group
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.base import DenseSurrogate
from archlux.light.evaluation import orientation_sector
from archlux.light.split_flux import SplitFluxOracle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
N = int(sys.argv[2]) if len(sys.argv) > 2 else 400
SEED, K = 17, 5
oracle, analytic = SplitFluxOracle(), AnalyticSurrogate()
variants = rs.four_room_variants(N, seed=SEED)
split = split_by_group([v.id.source for v in variants], seed=SEED, fractions=(0.5, 0.0, 0.0, 0.5))
train = [v for v in variants if v.id.source in set(split.groups["train"])]
test = [v for v in variants if v.id.source in set(split.groups["test"])]
check_no_group_leakage({"train": [v.id for v in train], "test": [v.id for v in test]})

xs, oris = [v.x for v in train], [v.orientation for v in train]
y_train = np.array([oracle.evaluate(v.x, v.orientation) for v in train])
models = {
    "analytic_affine": fit_affine(analytic, xs, oris, y_train),
    "dense": DenseSurrogate(),
    "ensemble": fit_dense_ensemble(xs, y_train, oris, k=K, seed=SEED),
}
models["dense"].fit(tuple(xs), y_train, tuple(oris), seed=SEED, epochs=60)  # type: ignore[union-attr]


def dominant(v: rs.RoomVariant) -> str:
    """Type of the largest room (the plan-level label of light.evaluation)."""
    areas = [v.x[4 * k + 2] * v.x[4 * k + 3] for k in range(len(rs.ROOM_IDS))]
    return v.room_types[int(np.argmax(areas))]


truth = np.array([oracle.evaluate(v.x, v.orientation) for v in test])
preds = {name: [m.evaluate(v.x, v.orientation) for v in test] for name, m in models.items()}
labels = {
    "orientation": [orientation_sector(v.orientation.deg) for v in test],
    "dominant_room_type": [dominant(v) for v in test],
    "glazing": ["not represented (no openings; oracle ignores glazing)"] * len(test),
}
ids = [v.id.key for v in test]
clusters = [v.id.source for v in test]
bd.write_breakdown_rows(OUT / "j7_sd_groups_raw.csv", ids, clusters, preds, truth, labels)

# Per room: the analytic surrogate rescaled per room (one scale, one offset), unit = room.
raw = np.concatenate([analytic.evaluate_rooms(v.x, v.orientation) for v in train])
room_y = np.concatenate([oracle.evaluate_rooms(v.x, v.orientation) for v in train])
scale, offset = np.polyfit(raw, room_y, 1)
room_pred = np.concatenate(
    [offset + scale * analytic.evaluate_rooms(v.x, v.orientation) for v in test]
)
room_truth = np.concatenate([oracle.evaluate_rooms(v.x, v.orientation) for v in test])
room_labels = {
    "room_type": [t for v in test for t in v.room_types],
    "orientation": [orientation_sector(v.orientation.deg) for v in test for _ in rs.ROOM_IDS],
}
room_ids = [f"{v.id.key}/{r}" for v in test for r in rs.ROOM_IDS]
room_clusters = [v.id.source for v in test for _ in rs.ROOM_IDS]
bd.write_breakdown_rows(
    OUT / "j7_sd_groups_rooms_raw.csv",
    room_ids,
    room_clusters,
    {"analytic_affine_per_room": room_pred},
    room_truth,
    room_labels,
)

head = "# B7 breakdown against the closed form (not against simulations)\n\n"
head += f"{N} typed four-room synthetic source plans x 4 azimuths, split by source "
head += f"(train {len(split.groups['train'])} / test {len(split.groups['test'])} sources), "
head += f"seed {SEED}. Reference: frozen `SplitFluxOracle`, a closed form: these errors say how "
head += "well a surrogate reproduces that oracle, **not** daylight. Intervals resample "
head += "whole source plans. Glazing is not represented (no openings, oracle ignores "
head += "glazing): that breakdown needs the Swiss Dwellings run of `j7_sd_labels.py`.\n\n"
body = ""
for name, p in preds.items():
    body += f"## Plan level: `{name}`\n\n"
    body += bd.to_markdown(bd.breakdown(p, truth, clusters, labels, seed=SEED), unit="score")
    body += "\n"
body += "## Room level: analytic surrogate rescaled per room\n\n"
body += bd.to_markdown(
    bd.breakdown(room_pred, room_truth, room_clusters, room_labels, seed=SEED), unit="score"
)
(OUT / "j7_sd_groups.md").write_text(head + body, encoding="utf-8")

params = {"n_sources": N, "azimuths": 4, "fractions": (0.5, 0.0, 0.0, 0.5), "ensemble_k": K}
params |= {"dense_epochs": 60, "room_affine": (float(scale), float(offset))}
outputs = [
    OUT / "j7_sd_groups_raw.csv",
    OUT / "j7_sd_groups_rooms_raw.csv",
    OUT / "j7_sd_groups.md",
]
command = f"python experiments/j7_sd_groups.py {OUT} {N}"
run = repro.record(seed=SEED, command=command, parameters=params, outputs=outputs)
repro.write_record(OUT / "j7_sd_groups_manifest.json", run)
