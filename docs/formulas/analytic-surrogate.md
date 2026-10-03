# Analytic surrogate

**Code:** `light.analytic.AnalyticSurrogate`.

## Statement

For each room, the vector \((x,y,w,h)\) and the azimuth \(\theta\) (through
[`encode_orientation`](circular.md), never the raw degree) give a score

\[
f_i=L\cdot\min(P,D)\cdot\exp(\kappa\,s),\qquad
L=w\cos^2\theta+h\sin^2\theta,\quad
P=w\sin^2\theta+h\cos^2\theta,
\]

where \(D=2.5\times 2.15\times F_{\mathrm{sector}}\) is the useful depth
modulated by eight sectors, and \(s\) the coordinate towards geographic south:

\[
s=-x\sin\theta-y\cos\theta.
\]

The surrogate returns \(\sum_i f_i\) (sDA, UDI, view) or its opposite (ASE).

## Assumptions

- The vector follows the \((x,y,w,h)\) per-room contract, same order as the polytope.
- The \(2.5\times\) head-height rule is **empirical** (CIBSE LG10); typical
  uncertainty \(\sim 30\,\%\). It is **not** a performance guarantee.
- \(\kappa=0.15\,\mathrm{m}^{-1}\) breaks translation invariance: without
  it, a *global* orientation factor would not change the argmax.

## Derivation

The south facade of an aligned rectangle is \(w\) if \(+y\) is north
(\(\theta=0\)) and \(h\) if the building has turned by \(90^\circ\). Hence
\(L=w\cos^2\theta+h\sin^2\theta\). The associated depth is the other
dimension. \(\min(P,D)\) is the useful-depth rule: beyond \(D\),
going deeper adds no more light. The subgradient at \(P=D\) is \(\{0,1\}\).

The gradient is computed by the product rule; a test compares it with
centred finite differences.

## Code

`AnalyticSurrogate.evaluate`, `.gradient`, `.uncertainty`.
Constants: `FACTEUR_PROFONDEUR`, `HAUTEUR_LINTEAU`, `KAPPA_SUD`,
`FACTEURS_SECTEUR` — `ClassVar`, never magic numbers in the body.

## Use cases

| Do | Do not |
|---|---|
| Validate the Frank-Wolfe flow before any learning | Publish the score as a measured sDA |
| Check that north and south *move* the plan | Encode \(\theta\) as a real number in \([0,360]\) |

## Source

Useful-depth rule: CIBSE, *Lighting Guide 10: Daylighting — a guide
for designers*, London. Harmonics: [circular](circular.md).
The vector protocol: `ARCHITECTURE.md` §10.
