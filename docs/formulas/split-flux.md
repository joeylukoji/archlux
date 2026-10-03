# Daylight factor (split-flux)

**Code:** `light.split_flux.daylight_factor`, `light.split_flux.SplitFluxOracle`.

## Statement

For a rectangular room with sides \(w,h\) (metres) and an azimuth \(\theta\),
the average daylight factor, as a **fraction** (2 % \(\mapsto 0.02\)),
is

\[
\mathrm{DF}=\frac{1}{100}\,\frac{T\,A_w\,\vartheta}{A_{\mathrm{surf}}(1-R^2)},
\qquad
A_w=\rho\,H_v L,\quad
L=w\cos^2\theta+h\sin^2\theta,
\]

\[
A_{\mathrm{surf}}=2wh+2(w+h)H_p,\qquad
\vartheta=\vartheta_0 F_{\mathrm{sector}}(\theta).
\]

\(\rho\) is the WWR (default \(0.30\)), \(H_v=1.15\,\mathrm{m}\) the glazed
height, \(H_p=2.70\,\mathrm{m}\) the ceiling height, \(T=0.70\),
\(R=0.50\), \(\vartheta_0=65^\circ\) (unobstructed sky).

`SplitFluxOracle` adds \(\sum_i 100\cdot\mathrm{DF}_i\cdot w_i h_i\) to the
analytic surrogate (CIBSE depth). It is **not** an LM-83 sDA.

## Assumptions

- CIE overcast sky; no urban obstruction other than \(F_{\mathrm{sector}}\).
- One window per room, centred on the south facade of the rectangle (WWR), without
  widening the vector protocol.
- Uniform reflectances. Transmittance without dirt (maintenance factor M omitted, \(=1\)).

## Derivation

The Littlefair / BRE formula for the average DF of a side-lit room lights
\(A_w\) under a sky angle \(\vartheta\) (degrees) and spreads the flux over
all internal surfaces. The factor \(1/100\) converts the CIBSE percentage
into a fraction. \(L\) is the same south facade as the [analytic surrogate](analytic-surrogate.md).
The derivatives \(\partial\mathrm{DF}/\partial w\) and \(\partial\mathrm{DF}/\partial h\)
follow the quotient \(u/v\).

## Code

`daylight_factor`, `SplitFluxOracle.evaluate`, `.gradient`.

## Use cases

| Do | Do not |
|---|---|
| CI oracle in place of a ray tracer | Publish the score as a measured sDA |
| Check: deeper → DF ↓; south > north; WWR ↑ → DF ↑ | Encode an image or an annual climate |

## Source

Littlefair, P. J. (2011). *Site layout planning for daylight and sunlight*
(BRE 209, 2nd ed.). IHS BRE Press. Average DF formula, overcast sky.
Sky angle and WWR: CIBSE, *Lighting Guide 10* (2014), see
[bibliography](sources.md) no. 15 and 16.
