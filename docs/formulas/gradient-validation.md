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
