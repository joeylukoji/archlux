# MSD — Modified Swiss Dwellings

The reference **geometry** corpus of the recent literature: annotated load-bearing
walls and columns, zoning graphs, preserved cardinal orientation, non-Manhattan
geometry. **It contains no daylight simulation** — its parent corpus,
[Swiss Dwellings](swiss-dwellings.md), carries them.

## Sheet

| Item | Value |
|---|---|
| Authors | van Engelenburg, C., Mostafavi, F. *et al.* (2024), ECCV |
| Paper | [arXiv:2407.10121](https://arxiv.org/abs/2407.10121) · [doi:10.1007/978-3-031-73636-0_4](https://doi.org/10.1007/978-3-031-73636-0_4) |
| Project page | <https://caspervanengelenburg.github.io/msd-eccv24-page/> |
| Code | <https://github.com/CasperVanEngelenburg/MSD> |
| Download | Kaggle: `caspervanengelenburg/modified-swiss-dwellings` |
| Size | 5,372 floor plans, > 18,900 distinct apartments |
| Derived from | Swiss Dwellings **v3.0.0** |
| Licence | **CC BY-SA 4.0** (Kaggle sheet, checked through the API). **Not** the CC BY 4.0 of the parent corpus |
| Redistributed here | **no** |

!!! warning "Share-alike"
    MSD is under **CC BY-SA 4.0**, while its parent corpus
    [Swiss Dwellings](swiss-dwellings.md) is under CC BY 4.0. The `SA` is a
    **share-alike** clause: it propagates to derived works. If the model
    or the published results must stay freely reusable without this
    constraint, train on Swiss Dwellings directly and use MSD only for
    the comparison geometry.

## Content

Three linked modalities: **image**, **geometry**, **graph**. The graph
(`networkx.Graph` or `torch_geometric.data.Data`) carries room shape and type on
the nodes, connection type on the edges, and the image of the whole plan at graph level.

For `archlux`, only the **geometry** modality is usable: the image is a
raster, and a surrogate with raster input has a zero gradient almost everywhere
(`ARCHITECTURE.md` §10, first anti-pattern).

## What MSD brings to `archlux`

- **No load-bearing annotation.** MSD separators are only `WALL` or `COLUMN`, so
  `Structure.load_bearing_walls` stays empty on this corpus (see `data/loaders.py`);
  the load-bearing guarantee is exercised by the synthetic benchmark instead
  (`benchmarks/guarantees`). Columns are loaded but not constrained (ADR-7).
- **Non-Manhattan geometry** → exercises `geom.rectilinear.decompose` on something
  other than a test case.
- **Preserved cardinal orientation** → `Orientation` is no longer drawn at random.
- **Multi-dwelling complexes** → relative orders far richer than
  the 2×2 tilings of the [synthetic corpus](synthetic.md).

## What it does not bring

No daylight label. The pairing goes through the Swiss Dwellings identifiers
from which MSD is derived — this is the recommended route, and it is described
in [ground truth](ground-truth.md).

## Cite

> van Engelenburg, C., Mostafavi, F., *et al.* (2024). *MSD: A Benchmark Dataset
> for Floor Plan Generation of Building Complexes*. ECCV 2024.
> [doi:10.1007/978-3-031-73636-0_4](https://doi.org/10.1007/978-3-031-73636-0_4)

**See also:** [Swiss Dwellings](swiss-dwellings.md),
[imputation](imputation.md), [ground truth](ground-truth.md).
