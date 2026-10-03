# IFC / DXF export and survival

**Code:** `export.to_ifc`, `export.to_dxf`, `export.survival_rate`.

## Statement

A plan is **exportable** if it shows no blocking pathology
(zero-length edge, duplicated vertices, self-intersection, non-closed solid,
overlap, non-positive dimension).

The **survival rate** of a sample of \(n\) plans is

\[
\hat p = \frac{k}{n},
\]

where \(k\) is the number of exportable plans. The confidence interval is the
**Wilson** one (not the normal approximation):

\[
\frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n}+\frac{z^2}{4n^2}}}{1+\frac{z^2}{n}}.
\]

The bounds stay in \([0,1]\) even for small \(n\) or extreme \(\hat p\).

## Assumptions

- Rectangular geometry (rooms = boxes); minimal IFC4 SPF without `bim`.
- The ``archlux[bim]`` extra loads `ifcopenshell` if available (writing stays
  deterministic SPF in CI).
- The certificate, if any, is attached as `Pset_Archlux` (text), not recomputed.

## Code

| Symbol | Function |
|---|---|
| diagnostic | `diagnose` |
| IFC | `to_ifc` → `ExportReport` |
| DXF | `to_dxf` |
| Wilson | `wilson_interval` |
| survival | `survival_rate` |

## Use cases

| Do | Do not |
|---|---|
| Publish \((\hat p, [lo, hi])\) Wilson | Normal interval (negative bounds) |
| Refuse to write if `validate=True` | Export a pathological plan "silently" |
| Attach the certificate report | Mix exact guarantee and performance in the IFC |

## Source

Wilson, E. B. (1927), *JASA* 22(158), 209-212 - [bibliography](sources.md)
no. 18. Why not the Wald interval: Brown, Cai & DasGupta (2001),
*Statistical Science* 16(2), no. 19. Repository protocol: `MILESTONE-6.md` §4.
