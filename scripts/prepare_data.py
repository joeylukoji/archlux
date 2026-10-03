"""Prepare the synthetic corpus and write the splits. Public API + data."""

from __future__ import annotations

from pathlib import Path

from archlux.bench.protocol import load_split
from archlux.data.synthetic import generate_corpus

root = Path("donnees/v1")
for name in ("train", "calibration", "test"):
    (root / name).mkdir(parents=True, exist_ok=True)
corpus = generate_corpus(90, seed=17)
split = load_split(Path("splits/v1"))
for identifier, plan in corpus.items():
    if identifier in split.train:
        target = root / "train"
    elif identifier in split.calibration:
        target = root / "calibration"
    else:
        target = root / "test"
    plan.to_json(target / f"{identifier}.json")
print("plans", len(corpus), "fingerprint", split.fingerprint)
