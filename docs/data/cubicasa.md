# CubiCasa5K

The **windows** side of the pairing: finely annotated doors and windows, where
simulated corpora often omit them.

## Sheet

| Item | Value |
|---|---|
| Authors | Kalervo, A., Ylioinas, J., Häikiö, M., Karhu, A., Kannala, J. (2019) |
| Paper | [arXiv:1904.01920](https://arxiv.org/abs/1904.01920) |
| Code and download | <https://github.com/CubiCasa/CubiCasa5k> |
| Size | 5,000 annotated plans, > 80 object categories |
| Format | **vector SVG** per image, semantic *and* geometric annotations |
| Licence | **research / non-commercial use** — read the repository's licence before any download |
| Redistributed here | **no** |

## What it brings

The annotations are **vector**, not raster: window segments can be projected
directly into `Opening(wall_id=..., s=..., relative_width=...)`. It is the only
corpus in this list that makes it possible to measure the difference between
**observed** windows and **imputed** windows — the measurement required by
[imputation](imputation.md).

## What it does not bring

- No daylight simulation.
- No reliable cardinal orientation (Finnish plans, north not guaranteed in
  the annotation): `Orientation` must be filled in or treated as missing.
- Scale in pixels, to be converted to metres before any use
  (`ARCHITECTURE.md` §7: units in metres, no exception).

!!! warning "Licence"
    The non-commercial licence of CubiCasa5K contaminates any model trained
    on it. If the published surrogate must be reusable, train on
    [Swiss Dwellings](swiss-dwellings.md) (CC BY 4.0) / [MSD](msd.md) (CC BY-SA 4.0) and use
    CubiCasa5K only for the **ablation study** on windows.

## Cite

> Kalervo, A., Ylioinas, J., Häikiö, M., Karhu, A. & Kannala, J. (2019).
> *CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image
> Analysis*. SCIA 2019. [arXiv:1904.01920](https://arxiv.org/abs/1904.01920)

**See also:** [imputation](imputation.md), [ground truth](ground-truth.md).
