# Gradient validation

**Code:** `light.validation.validate_gradient`.

## Statement

For a point \(x\) and a direction \(e_i\), the actual slope of the simulator is

\[
\widehat{\partial_i f}(x)
=\frac{f(x+\delta e_i)-f(x-\delta e_i)}{2\delta}.
\]

The **sign agreement** is the fraction of coordinates such that
\(\mathrm{sign}(\nabla \hat f_i)=\mathrm{sign}(\widehat{\partial_i f})\).

| Agreement | Decision |
|---|---|
| \(> 0.90\) | continue |
| \(0.80\)–\(0.90\) | continue while monitoring |
| \(< 0.80\) | **stop** — do not open milestone 5 |

## Assumptions

- The simulator is deterministic (otherwise the slope is not defined).
- \(\delta=0.10\,\mathrm{m}\) for the checkpoint (not a numerical
  \(\varepsilon\)).
- Evaluation goes through the simulator, never through the network.

## Source

`MILESTONE-4.md` §7. Centred finite differences: Nocedal & Wright,
*Numerical Optimization*, Springer, §8.1.

## Beyond the checkpoint: reliability and run-time refusal

**Code:** `light.trust` (`gradient_agreement`, `gradient_reliability`,
`step_gain_audit`, `gradient_trust`, `GuardedSurrogate`,
`FiniteDifferenceSurrogate`); experiment `experiments/j4_reliability.py`.

`validate_gradient` is a gate on a handful of points. A surrogate can pass it
and still point the wrong way on the plans the optimizer actually visits, so
the same comparison is also run:

- **per group**: azimuth sector, room type, window configuration;
- **per amplitude**: \(\delta \in \{0.02, 0.10, 0.50\}\,\mathrm{m}\);
- **on optimized plans**, not only on held-out ones;
- **per step**: for each Frank-Wolfe step \(x_k \to x_{k+1}\), the gain the
  surrogate predicted, \(\hat f(x_{k+1})-\hat f(x_k)\), against the gain the
  reference realised, \(f(x_{k+1})-f(x_k)\).

Measured with the j4 network, the frozen split-flux oracle as reference
(`results/j4_reliability.csv`, seed 17):

| Plans | Sign agreement (all) | Sectors of 45° passing 0.80 |
|---|--:|--:|
| 80 held-out | 0.827 | 4 / 8 (0°, 45°, 90°, 270° fail) |
| 16 Frank-Wolfe outputs | 0.935 | 6 / 7 present (90° fails) |
| 125 Frank-Wolfe steps, predicted vs realised gain sign | **0.552** | — |

The amplitude barely changes these numbers: the oracle is smooth at these
scales. The step audit is the most telling: the sign of the gain the
surrogate announced for a step matches the sign of the realised gain only
slightly more often than a coin flip.

**Run-time refusal.** `gradient_trust` returns `"ok"` or `"refuse"` (sign
agreement below the threshold, or a flat reference) without raising.
`GuardedSurrogate` applies it at every gradient call and is passed to
`legalize` as an ordinary objective: on refusal it returns a zero gradient,
so Frank-Wolfe sees a zero duality gap and stops at the current point (the L1
plan if the first gradient is refused), or it raises `UntrustedGradient`.
`GuardedSurrogate.history` records every verdict. Caveat: the trace then
reports `converged`, a status that does not say *why*; read `history`.

**Gradient-free baseline.** `FiniteDifferenceSurrogate(base)` makes any
deterministic evaluator a surrogate whose gradient is its own centred finite
differences: the same Frank-Wolfe, no learned direction. With the oracle as
`base` it reproduces the oracle-optimized plans (test
`test_the_gradient_free_baseline_matches_the_analytic_gradient`).

All of this is against a **closed-form** reference. It measures the
surrogate's fidelity to the oracle, not to physics.
