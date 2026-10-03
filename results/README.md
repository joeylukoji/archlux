# Raw results

Results are written **here, in raw form, before any aggregation**.

A published mean without its underlying data cannot be checked. Every file carries its
seed and the fingerprint of the split it used.

## Where to look

| | |
|---|---|
| [`j8_generation.md`](j8_generation.md) | milestone 8 summary: legalization of **actually generated** plans |
| [`visuals/`](visuals/index.md) | **before / after** comparisons plan by plan, metrics attached, failures included |

A rate does not say what a repair looks like: `visuals/` is there so that "plan
certified valid" and "median displacement of 43 % of the side" are read together and
not one without the other. Looking at these sheets is how rooms were seen to
disappear, a defect that none of the tables showed.

## Synthetic and corpus results

- **Synthetic** (milestones 2 to 6: `j2_*`, `j3_*`, `j4_*`, `j5_*`, `j6_*`): regenerated
  by `python scripts/results.py` and fingerprinted in `SHA256SUMS`;
  `python scripts/results.py --check` reproduces them byte for byte.
- **Corpus** (milestones 7 to 9: `j7_*`, `j8_*`, `orientation/`, `visuals/`): need the
  MSD, Swiss Dwellings and HouseDiffusion data, which are not redistributed
  (`docs/data/`). Their text was **translated to English without re-running** (chantier
  E, wave 4): headings, labels and prose now match what the translated scripts write,
  and every number is unchanged (checked digit by digit). They are regenerated at the
  phase-2 corpus run. Until then:
  - lines produced by the library rather than by the scripts keep the wording of the
    original run: the loading summary of `j7_msd_idempotence.md` (`LoadStatistics`, still
    French in `src/`), the violation lines of the `visuals/` sheets (two decimals; the
    library now prints four), and the Farkas origin quoted in `j8_generation.md`;
  - files written by an older version of a script keep its layout: `j7_repair.md`
    (hand-written, with a timing column; `experiments/j7_msd_summary.py` rebuilds its
    table from `j7_repair_raw.csv`), `j7_sd_per_room.md`, `j7_variance.md`,
    `j8_generation.md` and `visuals/index.md` (hand-written syntheses),
    `j8_pilote.md` and the `j8_pilote` / `j8_generation` raw files (pilot run, fewer
    columns);
  - published CSV **values** are kept as data: fault modes (`retrecir`, `deplacer`, ...),
    `mode` (`base`, `pavage`), `status` (`infaisable`, `trame`, `invariant_viole`), the
    `pavage` column of `j7_repair_raw.csv`. CSV **column names** are English.
- `etoile`, `plausible`, `divers`, `pilote` and `generation` are dataset **labels** (the
  third argument of `experiments/j8_generation.py`, `--label` of `scripts/results.py`,
  and the `graph` values of the JSONL files): they name files and folders as they are.
