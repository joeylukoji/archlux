# Reproducing the results

Everything a third party needs to regenerate the published numbers, and what it cannot
regenerate without restricted data. The reference table of commands, data and outputs
is [`docs/formulas/benchmark.md`](docs/formulas/benchmark.md#reproduce); this page adds
the environment and the checks.

## Environment

| Item | Value used for `results/` |
|---|---|
| Python | 3.13 (CI also runs 3.11 and 3.12) |
| numpy / scipy / shapely / networkx / ortools | 2.5.3 / 1.18.1 / 2.2.0 / 3.7 / 9.15.6755 |
| OS / CPU | Linux x86_64 (timings: one Windows 11 machine, see `results/j9_timing_raw.csv`) |
| Install | `pip install -e ".[dev]"`, or `docker build -t archlux . && docker run --rm archlux` |
| Seeds | root seed 17 everywhere; sub-seeds through `archlux.seeds.derive(17, name)` |

Each run of the newer benches writes a manifest (`results/*_manifest.json`): git commit
and dirty flag, dependency versions, platform, seed, command, parameters and the SHA-256
of inputs and outputs.

## Commands

| What | Command | Data | Check |
|---|---|---|---|
| B1-B5, B3 extended, B8 failure classes, B9 three states, naive baseline | `make results` | none | `make check-results` (byte-for-byte against `results/SHA256SUMS`) |
| Coverage after selection, 200 draws, ablations, reconciliation | `make reproduce` | none | `results/RECONCILIATION.md` |
| Every table of the paper | `make paper` | none for the synthetic benches | |
| Frozen reference cases | `pytest -m reference` | none | five JSON files in `tests/references/` |
| B6 (MSD), B7 (Swiss Dwellings), B8 (HouseDiffusion) | see `docs/formulas/benchmark.md` | restricted, below | rerun and compare the summaries |
| Physical check of B9 (Radiance) | `python experiments/b9_three_states.py results` with `oconv`, `rtrace`, `gensky` on PATH | none | column `reference` = `physical` |

## Data that cannot be redistributed

| Corpus | Licence | Why it is not in the repository | How to rebuild |
|---|---|---|---|
| MSD | see `docs/data/msd.md` | redistribution restricted | download, then `scripts/prepare_data.py` |
| Swiss Dwellings v3.0.0 | CC BY 4.0, raw rows large | the per-room rows are not mirrored here | download from Zenodo (doi:10.5281/zenodo.7788422) |
| HouseDiffusion outputs | GPL (model) | generated with the official weights; the model is GPL | `docs/data/` and `experiments/j8_generation.py` |

The raw rows derived from these corpora that are publishable (`j7_*`, `j8_*`) are in
`results/`; the summaries are recomputed from them by `make reconcile`.

## Known limits of reproducibility

- LP solvers can return a different optimal vertex on degenerate problems; the reference
  cases round to the micrometre, but a different OR-Tools version may still move a
  degenerate solution.
- Timings depend on the machine; they are orders of magnitude, not benchmarks.
- No Radiance run is published yet: the physical check above is ready, not done.
