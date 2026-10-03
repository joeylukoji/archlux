# Limitations

**To read before any professional use.** This page is mandatory, not optional:
a tool that produces regulatory numbers must say explicitly what it does not
check.

## Early-design estimates

The indicators produced are **early-design estimates**. They do not replace a
regulatory thermal or daylight study. The bound of milestone 5 covers
the frozen oracle (`SplitFluxOracle` split-flux / analytic), **not** an LM-83 sDA
(Radiance). `sim` extra: empty on purpose.

## On a generator output, the closest valid plan is not close

**This is the limitation that decides the real use of the legalizer, and it is measured.**

Milestone 7 repairs 93.9 % of MSD plans **corrupted by hand**, moving little.
Milestone 8 redoes the measurement on **really generated** plans — HouseDiffusion (CVPR
2023), official weights, 1000 steps, 740 plans under three conditionings. The regime is
not the same:

| on the generator outputs | median |
|---|--:|
| valid plans before repair | **0 / 740** |
| rooms overlapped per room | 0.80 |
| share of gap in the envelope | 28.6 % |
| disjoint fragments of the union | **4** |
| cells of the implicit grid (6 rooms) | **80** |

A corrupted plan is a valid plan one of whose dimensions has moved: its grid exists, it
only has to be found again. A generator output has **no grid** — its rooms share
almost no line, the union falls into four fragments, and the combinatorial structure
that `geom.tiling` exploits is not merely violated, it is absent.

Quantified consequences, at repair budget 16 and `min_width = 0.50 m`:

- `legalize` alone repairs **0.0 %** — expected: a gap is a stationary point of
  the L1 optimum, exactly what `tiling` exists to correct;
- `legalize(tiling=True)` repairs **17.8 to 23.0 %** depending on the conditioning,
  moving **38 to 43 % of the side** of the plan. The result is a valid plan *in the
  neighbourhood* of the generated plan, not the generated plan repaired;
- **without a floor on the width, this rate rises to ~60 % — and it is an illusion.**
  Closing a gap by shrinking a room to zero is the cheapest solution: 61 %
  of the plans then deemed repaired carried at least one room with a side of **exactly
  zero**, and came out certified valid, amputated. Counting the rooms does not detect it.
  The rate is **flat from 0.25 m to 1.80 m**: this is not a threshold calibration but a
  binary choice, to allow degenerate solutions or not;
- the rate drops with the size of the program, because the grid swells as
  \\((2n-1)^2\\) when no edge coincides, while the bounded repair only
  corrects a bounded number of cells;
- some plans are **proved infeasible**: the repaired grid then contradicts the
  separations from `deduce_order`, and the Farkas certificate names the minimal
  conflict (2 to 3 rows out of 45).

What this means for a user: **a-posteriori legalization does not replace
a generator that respects the tiling condition.** It guarantees validity and
proves it; it guarantees neither resemblance nor the survival of the program, and the
latter must be asked for explicitly, with a strictly positive `min_width`. The
constraint belongs *in* the generator — which this repository makes it possible to
quantify, not what it provides.

Details, protocol and before / after comparisons plan by plan:
`results/j8_generation.md` and `results/visuals/`.

## The surrogate predicts at the wrong granularity

**This is the deepest limitation of the project, and it is measured.**

The `Surrogate` protocol returns **one scalar per plan**. Daylight is a quantity
**per room**. Variance decomposition over 367,466 rooms of Swiss Dwellings,
target `sun_201803211200_mean`:

| fixed effect | groups | \(R^2\) |
|---|--:|--:|
| building identity | 3,171 | **0.026** |
| building × floor | 13,688 | 0.068 |
| apartment identity | 44,888 | **0.077** |
| floor number alone | — | 0.004 |

**92 % of the variance is within-apartment**, between rooms. Aggregating into a
dwelling mean therefore amounts to predicting a quantity whose variance weighs only
7.7 % of the phenomenon: the rest is smoothed out by the aggregation itself.

This is what explains the measured \(R^2 \approx 0\) — analytic \(-0{,}000\),
perceptron \(-0{,}557\), perceptron with windows \(-0{,}220\) — much more than the
poverty of the inputs. Enriching the input really helps (the windows close 60 % of
the gap) but attacks the wrong problem.

Practical consequence: **no sDA-type indicator can be represented** by this
protocol. sDA is defined per room — share of the floor above 300 lux — never per
dwelling. A useful surrogate would return a vector, one value per room, and Frank-Wolfe
would optimize an explicit scalarization of these values.

## The urban mask is not the missing factor

The hypothesis was natural, and two independent checks refute it.

Building identity — which carries the urban mask, the climate and the solar position —
explains only **2.6 %** of the variance. And the climate normals do not correlate:
`climate_snorm_year` gives \(r = -0{,}06\), `climate_snorm_march` \(r = +0{,}05\).
The target is a **geometric** ray tracing at fixed solar position, not a
meteorological quantity.

No geometry of the built environment is published in the corpus anyway: the
mask exists only in the simulation outputs. Using it as an input would require
simulating in order to predict, which empties the surrogate of its reason to exist.

Details and protocol: `results/j7_variance.md`.

## The learned surrogate has never seen a measurement

The labels **shipped in this repository** come from
`light.split_flux.SplitFluxOracle`, a **closed form** (CIBSE analytic +
BRE split-flux). The perceptron `light.base.DenseSurrogate` learns the *residual* between
this closed form and `AnalyticSurrogate`: two known formulas, on 90 2×2 tilings
with two degrees of freedom, without walls or openings.

Real labels are now reachable — `data.loaders` joins MSD to the
Swiss Dwellings simulations, 18,263 apartments out of 18,270 — but they are not
redistributed, and the measurement made against them is a **negative result**: see
above.

In other words: the chain tokenization → training → freeze → conformal calibration →
Frank-Wolfe is **exercised end to end**, and no physical quantity has been
measured. The transformer announced at milestone 4 does not exist — `LearnedSurrogate`
refuses `.pt` weights.

Any coverage reported by this repository is therefore a coverage **on the frozen oracle**,
never on observed daylight. The sources of real labels and their cost are
detailed in [ground truth](data/ground-truth.md).

## Exchangeability and selection

The performance guarantee assumes **exchangeability** with the calibration set.
Plans produced by an optimizer are *selected* to maximize the
prediction: the real coverage under this selection is an open research
question, measured and published by the project (drift, benchmark).
The certificate says so: the bound of a plan returned by `legalize` carries
`regime="selected"`, and the report writes "coverage NOT guaranteed" instead of a
percentage. For an exchangeable plan, if drift is detected, the certificate
shows `NOT EVALUABLE` rather than a misleading interval.

## Load-bearing structure: what is and is not certified

Since 0.10 (ADR-7), the certificate proves that **no room crosses a load-bearing wall**,
and the solver keeps every room on its side of each wall. It does not certify more:

- **Columns** (`Structure.columns`) are not constrained or checked: a column inside a
  room is normal in housing, and nothing is claimed about them.
- **Openings on interior partitions do not follow a moved room**: walls are not decision
  variables. Openings on facades stay put because the outline is fixed.
- **Oblique load-bearing walls are refused** (`UnsupportedInput`) rather than ignored:
  no linear side constraint keeps a rectangle off an oblique segment exactly.
- Each room keeps **one** side of each wall, read from the proposed plan: a valid
  arrangement on another side of a partial wall is not explored.

## `NOT EVALUABLE`

The **`NOT EVALUABLE`** field covers the articles whose check requires
information absent from the plan — materials, technical systems, summer comfort —
or a regulatory interpretation. It is not a forgotten computation: it is an
explicit refusal to invent a coverage.

## Not legal advice

The check computes predicates on a geometry (and, where applicable,
a probabilistic bound on a frozen oracle). **It does not constitute legal
advice** nor an administrative certificate of compliance.

## What automatic checking cannot establish

- That the plan can be built in the site sense (tolerances, phasing, services).
- That the imputed openings (if the corpus is incomplete) match the real building.
- That an IFC export "valid" in the sense of the `archlux` pathologies is accepted by
  every third-party BIM tool without reprocessing.
- That a 90 % conformal coverage on the frozen oracle holds for another climate,
  another use, or another generator outside the calibration distribution.

> A plan produced by this system is a proposal, never a project document.

API **not frozen**: development version `0.10.0.dev0`, 1.0.0 is postponed to the end of phase 5 of `PLAN.md`; checklist outside the code:
[release 1.0](release-1.0.md).

**See also:** [The two guarantees](concepts/two-guarantees.md),
[Contributing](contributing.md).
