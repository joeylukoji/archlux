# Corpora

The **train / calibration / test** sets are lists of identifiers published
in `splits/v1/`. **Deduplicate before splitting**, never the other way round.

| Sheet | What it brings | Licence | In this repository |
|---|---|---|---|
| [**Ground truth**](ground-truth.md) | **where the daylight labels are** | — | method |
| [Synthetic](synthetic.md) | deterministic 2×2 tilings, CI stand-in | Apache-2.0 | yes, generator |
| [Swiss Dwellings](swiss-dwellings.md) | **paired geometry ↔ daylight**, 367 simulation columns | CC BY 4.0 | not redistributed |
| [MSD](msd.md) | load-bearing walls, non-Manhattan, cardinal orientation | **CC BY-SA 4.0** | not redistributed |
| [CubiCasa5K](cubicasa.md) | annotated windows, vector SVG | research / non-commercial | not redistributed |
| [Window imputation](imputation.md) | incomplete corpus → default windows | — | method |

!!! warning "Start with the ground truth"
    The shipped corpus (90 synthetic plans, labels from a closed form)
    runs the chain, **not an evaluation**. Before announcing a coverage
    number, read [ground truth](ground-truth.md): it says where the labels
    really come from and what one is entitled to conclude from them.

The calibration set can only be read with a token issued **after** the weights
are frozen (`uq.registry`).

## Provenance and splits by source plan

`data.provenance` keeps every sample traceable to the plan it came from:

- `SampleId(source, corruption, variant, run)`, key `source/corruption/variant/run`:
  the **source** is the dwelling, the statistical unit and the split key;
- `split_by_group(sources, seed=...)`: train / validation / calibration / test drawn on
  sources (40 / 10 / 25 / 25 % by default), ordered by a seeded hash so that adding a
  source never reshuffles the others;
- `check_no_group_leakage`: refuses a source present in two sets (eight azimuths of
  one dwelling in calibration and test would make the coverage about seen plans);
- `cross_split_near_duplicates`: near-duplicate source plans that ended up in
  different sets (the check that deduplication ran before the split);
- `FilterLog`: count before and after each filter, rendered as a table, so that a rate
  always comes with its denominator (MSD: 1 247 read until 400 were kept; the loader's
  `LoadStatistics` lists the rejection reasons).
