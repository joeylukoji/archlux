# Daylight ground truth — where the labels are

This page answers a single question: **what is the surrogate really trained
with?** It is the weakest link of the chain, and passing over it in silence
would invalidate any publication.

---

## 1. The current state of the repository, plainly

| Item | What is shipped |
|---|---|
| Corpus | 90 synthetic 2×2 tilings, fixed 12 m × 9 m envelope (`data.synthetic`) |
| Split | 54 / 18 / 18 (`splits/v1/`) |
| Labels | `light.split_flux.SplitFluxOracle` — **a closed form** |
| Model | `light.base.DenseSurrogate`, 3-layer perceptron, `numpy` weights |
| Learned target | the **residual** `SplitFluxOracle − AnalyticSurrogate` |

Both terms of this residual are analytic. The network therefore learns the
difference between two known formulas, on a family of plans with **two degrees
of freedom** (the two cut coordinates). The `mae_reseau = 0,0175` against
`mae_analytique = 6,4007` published at milestone 4 measures exactly that, **on the
training set**: a successful regression on a deterministic function, without noise.
These two numbers no longer reproduce with the shipped code (the same script gives
0.33 and 41.9); on a test set, in phase 2 (`results/j4_gradient.csv`, review
[j4](../revues/j4.md)), the network's error is 1.19 against 37.3.

!!! danger "What this means for a paper"
    This is **not** a learning result. No reviewer will accept
    "calibrated daylight surrogate" backed by labels produced by a
    closed formula that the base model already knows. The chain
    (tokenization → training → freeze → conformal calibration → Frank-Wolfe) is
    **exercised end to end**, which is a real engineering result; the
    physical quantity, however, has never been measured.

    Corollary: `LearnedSurrogate._charger_torch` **always raises**. The
    transformer announced at milestone 4 does not exist in the repository.

---

## 2. The three possible label sources, by increasing cost

### Option A — Swiss Dwellings (recommended to start)

**The only public source that delivers paired geometry and daylight.**

- 45,000 apartments, ≈ 250,000 rooms, **367 simulation columns per room**.
- Family `sun_YYYYMMDDHHMM`: solar irradiance (direct + diffuse) per
  floor hexagon, spring equinox and summer solstice.
- **CC BY 4.0**, direct download, neither request nor partnership.
- [doi:10.5281/zenodo.7788422](https://doi.org/10.5281/zenodo.7788422) — sheet:
  [Swiss Dwellings](swiss-dwellings.md).

| For | Against |
|---|---|
| No simulation to run | It is **not** an LM-83 sDA: these are aggregates at fixed instants |
| Enough volume for a real 60/20/20 split | Swiss climate only — out of distribution elsewhere |
| Windows and load-bearing walls present in `geometries.csv` | WKT → `Plan` reconstruction to write (does not exist in the repository) |
| Clean licence, republishable model | The urban mask is included in the simulation, not in the input vector |

**Mandatory consequence:** rename the target. `indicator="sDA"` becomes a
lie as soon as one calibrates on `sun_*`. Publish "90 % coverage on
*Swiss Dwellings sun_mean, v3.0.0*", never "90 % coverage on the sDA".

### Option B — simulate yourself with Radiance

The only path to a **real sDA₍₃₀₀/₅₀ %₎** in the IES LM-83 sense.

- Geometry: [MSD](msd.md) or [CubiCasa5K](cubicasa.md) (annotated windows).
- Engine: Radiance / `rtrace` (`honeybee-radiance`, `ladybug-tools`), EPW climate.
- Cost: **minutes to hours per plan**. This is precisely what the surrogate
  exists to avoid — and it is what makes active learning (`archlux.active`)
  relevant rather than decorative.
- The `sim` extra of `pyproject.toml` is **empty on purpose**: the engine plugs in
  behind `light.split_flux` without touching the `Surrogate` protocol.

Order of magnitude for a paper: 2,000 to 5,000 simulated plans are enough for an
honest 60/20/20 split, with **n ≥ 500 in calibration** — at level α = 0.10,
\(\lceil (n+1)\cdot 0{,}90\rceil\) stays very far from \(n\), and the bound is no
longer dominated by sampling noise.

### Option C — incomplete corpus + window imputation

When the geometry comes from a corpus without windows: `data.imputation` centres a
window (`s = 0.5`, `relative_width = 0.30`) on each bare wall.

It is an **assumption**, not a measurement. The repository's rule still holds:
calibrate separately on the subset with observed windows and on the imputed set, and
**publish both coverages**. See [imputation](imputation.md).

---

## 3. What the synthetic corpus can and cannot do

`data.synthetic.generate_corpus` stays useful, and must stay:

- it runs CI without downloading gigabytes;
- it is deterministic, so the certificates are reproducible;
- it carries the duplicate `syn-0053` ≡ `syn-0000` that tests deduplication.

It cannot serve as an evaluation corpus:

- **no wall** (`walls=()`) and **no opening** (`openings=()`) — the window
  tokens of `light.tokens._jeton_ouverture` are therefore **never exercised** on
  the shipped corpus, and the WWR of `SplitFluxOracle` stays at its default value
  whatever the real fenestration;
- a single envelope, four rooms, two degrees of freedom;
- a single topology type (2×2 tiling), hence a single relative order.

---

## 4. Order of operations, no exception

```
inventory → deduplicate (Hausdorff 0.02 m) → split (60/20/20)
          → train on train → FREEZE the weights → issue the token
          → read calibration → conformal calibration → open test ONCE
```

Deduplicate **before** splitting. A duplicate straddling training and
calibration makes the announced coverage wrong — too optimistic — and **nothing
reports it**: neither the tests nor the review. It is the only silent error of the
system able to invalidate a published number (`ARCHITECTURE.md` §10).

The implementation lock is `uq.registry.issue_token`: the token can only be
issued after the fingerprint of the frozen weights.

---

## 5. What the join gave, once done

The loader now exists (`data.loaders.load_sd_labels`,
`label`, `split_by_site`) and the join works:

| | |
|---|--:|
| MSD apartments found in Swiss Dwellings | **18,263 / 18,270** |
| Habitable rooms paired | **98 – 99.5 %** depending on the type |
| Technical spaces (shafts, stairwells, lifts) | **0 %** — they have no daylight to simulate |
| Apartments paired in full | 5,817 |

Pitfall met: MSD writes `area_id` as a float (`484803.0`), Swiss Dwellings as an
integer (`484803`). Without normalization, the join returns **0 %**.

The result of the measurement is **negative**, and instructive — see
[limitations](../limitations.md): the granularity of the protocol, not the quality of
the data, is the limiting factor.

## 6. What is left to write in the repository

| Missing | Where it should live |
|---|---|
| WKT → `Plan` loader (Swiss Dwellings / MSD) | `data/loaders.py` (does not exist) |
| Projection of a WKT opening → `(wall_id, s, relative_width)` | same |
| Radiance runs on a glazed corpus | `light/radiance.py` exists (a `Reference`, not a `Surrogate`); no run has been made: the binaries are not installed in CI |
| Transformer on tokens | `light/learned.py` — today `_charger_torch` always raises |
| Coverage results on a real corpus | `results/` |

## 7. Surrogate against reference, and how to run Radiance

The code keeps the two apart in the types (`light.reference`):

| | Surrogate | Reference |
|---|---|---|
| Protocol | `Surrogate`: `evaluate`, `gradient`, `uncertainty` | `Reference`: `measure` → `ReferenceMeasure` |
| Returns | a prediction | a value with `unit`, `kind`, `engine`, `parameters` |
| Shipped | `AnalyticSurrogate`, `SplitFluxOracle`, `DenseSurrogate` | `ClosedFormReference` (`kind="closed_form"`), `RadianceReference` (`kind="physical"`) |

`light.evaluation.evaluate_surrogate` scores a surrogate on **held-out**
plans only (it raises on any id used for training or tuning): MAE, relative
error, bias, Pearson and Spearman, each with a bootstrap interval, overall and
per orientation sector, room type and window configuration. Absolute errors
are computed only when surrogate and reference share a unit; against Radiance
(lux) a surrogate trained on the oracle's score is judged by correlation only.

`light.evaluation.compare_before_after` takes the same plans before and after
optimization and returns, per plan, the predicted gain, the reference gain,
their gap and the displacement. `summarize_gains(...).claim` is
`"confirmed"` only when **every** row was measured by a physical reference
and the mean reference gain is positive; otherwise `"predicted"`. A gain
measured by the closed-form oracle is `closed_form_only`, never confirmed.

What the repository measures today (`results/j4_before_after.csv`, j4 network,
16 held-out plans, 45° sectors, reference = oracle): mean predicted gain
**9.1 %**, mean oracle gain **2.6 %**, so about 70 % of the announced
gain is the surrogate's own; 9 of the 16 optimized plans are flagged out of
distribution by `light.ood`. Until a physical reference has been run, a
figure such as "+17.2 % daylight" must be written **predicted**.

**Out of distribution.** `light.ood.fit_envelope` summarizes the training
plans in descriptor space (Mahalanobis distance, ridge on the covariance) and
sets its threshold by the finite-sample conformal quantile of a held-out
calibration set; `flagged_prediction` attaches the verdict to a prediction.
**Provenance.** `light.card.SurrogateCard` records the weights fingerprint,
the training-data fingerprint and ids, the label engine and its parameters,
the hyperparameters and the held-out metrics, and round-trips through JSON.

**Running Radiance.** Install Radiance 5.4+ so that `oconv`, `rtrace` and
`gensky` are on `PATH` (packages: `radiance` on Debian/Ubuntu, the NREL
installers otherwise; `pip install` alone does not provide the binaries).
Then:

```bash
python scripts/simulate.py --radiance        # -> results/j4_simulations_radiance.csv
pytest tests/unit/test_light_reference.py    # runs the integration test
```

`RadianceReference` builds one closed box per room (opaque partitions,
reflectances 0.2 / 0.5 / 0.8, glazing transmittance 0.6), cuts the openings of
the `Glazing` into the room edges they lie on, rotates the plan
counterclockwise by the azimuth (the convention of `AnalyticSurrogate`), and
traces a 0.5 m work-plane grid at 0.8 m under one `gensky` sky (default: Bern,
21 March, noon, clear with sun; `-ab 5 -ad 1024 -as 512 -ar 256 -aa 0.1`). It
returns the area-weighted mean illuminance in lux and the mean per room. It
is a **point-in-time illuminance**, not an LM-83 sDA (that needs an annual
`rfluxmtx` / `dctimestep` run over an EPW file). It refuses, rather than
returning zero, a plan without openings: the shipped synthetic corpus has
none, so every row of the `--radiance` run is `not_measured` until a glazed
corpus (MSD with windows, Swiss Dwellings) is loaded.

**See also:** [Swiss Dwellings](swiss-dwellings.md), [MSD](msd.md),
[CubiCasa5K](cubicasa.md), [synthetic](synthetic.md),
[imputation](imputation.md), [statistics](../formulas/statistics.md),
[limitations](../limitations.md).
