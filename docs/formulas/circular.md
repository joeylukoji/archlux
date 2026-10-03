# Circular statistics

**Code:** `orient.circular`.

## Statement

An azimuth \(\theta\) is a point on the circle. It is encoded by the harmonics

\[
\phi(\theta)=\bigl(\cos\theta,\;\sin\theta,\;\cos 2\theta,\;\sin 2\theta,\;\ldots\bigr)
\in\mathbb{R}^{2H},
\]

never by the raw degree. The mean of \(n\) azimuths is the argument of the
sum of the unit vectors:

\[
\bar\theta=\operatorname{atan2}\Bigl(\sum_i\sin\theta_i,\;\sum_i\cos\theta_i\Bigr),
\qquad
\bar R=\frac{1}{n}\Bigl\lVert\textstyle\sum_i(\cos\theta_i,\,\sin\theta_i)\Bigr\rVert.
\]

The circular variance is \(V=1-\bar R\). The Rayleigh test of uniformity
uses \(p\approx\exp(-n\bar R^2)\).

## Assumptions

- Angles in degrees on input, radians inside the trigonometric functions.
- \(H\ge 1\). A single harmonic does not separate east from west beyond the sign of \(\sin\).
- The Rayleigh test is an exponential approximation (large \(n\), or
  marked concentration). For \(n=5\) azimuths all pointing north, \(p<0.01\).

## Derivation

\(359^\circ\) and \(1^\circ\) are close: \(\cos 359^\circ\approx\cos 1^\circ\).
The arithmetic mean \((359+1)/2=180\) is the antipode — the trap that
`circular_mean([350, 10])` must avoid (result \(0^\circ\)).

The circular-linear regression is the least-squares fit

\[
y\approx a\cos\theta+b\sin\theta+c.
\]

## Code

`encode`, `encode_orientation`, `circular_mean`, `concentration`, `circular_variance`,
`rayleigh`, `circular_linear_regression`, `stratify`.

## Use cases

| Do | Do not |
|---|---|
| Pass every azimuth through `encode_orientation` before a model | Subtract degrees as if they were reals |
| Stratify a wind rose into 8 sectors | Believe that a Rayleigh \(p\) *proves* a physical cause |

## Source

Mardia & Jupp (2000), *Directional Statistics*, Wiley, ch. 2–3 and §6.3 (Rayleigh).
[Bibliography](sources.md) no. 11.
