# Preregistrations (PLAN.md phase 6)

Every phase-6 experiment is preregistered here **before** it is run: hypothesis, metric,
statistical test, sample size (computed with `archlux.bench.stats.power`), seeds and
split. A preregistration is frozen by the commit that adds it; a later change is a new
file that says what changed and why, never an edit. Results are published whatever they
say, negative ones included.

| File | Experiment | Status |
|---|---|---|
| [`6.1-per-room-surrogate.md`](6.1-per-room-surrogate.md) | Per-room surrogate and its scalarisation | Draft, to freeze |
| [`6.3-surrogate-vs-baselines.md`](6.3-surrogate-vs-baselines.md) | Surrogate against trivial baselines | Draft, to freeze |
| [`6.4-coverage-under-selection.md`](6.4-coverage-under-selection.md) | Conformal coverage under selection | Draft, to freeze |
| [`6.6-active-learning.md`](6.6-active-learning.md) | Active against random acquisition | Draft, to freeze |

Template: [`TEMPLATE.md`](TEMPLATE.md).
