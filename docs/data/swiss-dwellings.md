# Swiss Dwellings

**It is the only public corpus that carries the pair geometry ↔ daylight.** The others
give plans without daylight truth. Without it, the surrogate learns nothing
other than an already known closed formula — see [ground truth](ground-truth.md).

## Sheet

| Item | Value |
|---|---|
| Producer | Archilyse AG |
| Current version | **v3.0.0** (2023-03-31) |
| Size | ≈ 45,000 apartments, ≈ 250,000 rooms, ≈ 3,100 buildings |
| Licence | **CC BY 4.0** — research *and* commercial use, attribution mandatory |
| DOI (concept) | [10.5281/zenodo.7070951](https://doi.org/10.5281/zenodo.7070951) |
| DOI (v3.0.0) | [10.5281/zenodo.7788422](https://doi.org/10.5281/zenodo.7788422) |
| Redistributed here | **no** |

## Content

One zip, four CSV files:

| File | Granularity | Content |
|---|---|---|
| `geometries.csv` | element | **WKT geometries in metres**: rooms, walls, **openings**, fixtures |
| `simulations.csv` | room (`area`) | **367 simulation columns** per room |
| `locations.csv` | building | climate, context, accessibility |
| `location_ratings.csv` | building | location ratings |

Join: `site_id + building_id + floor_id + apartment_id + unit_id + area_id`
to link `geometries` to `simulations`; `building_id` for `locations`.

## What serves as ground truth

`simulations.csv` contains a **sun / daylight availability** family, named
`<category>_<dimension>_<aggregation>` (aggregations `min`, `max`, `mean`, `std`,
`median`, `p20`, `p80`), and dated columns of the form `sun_YYYYMMDDHHMM`
(e.g. `sun_201803210800` = 21 March, 8 am; `sun_201806210600` = 21 June, 6 am) —
spring equinox and summer solstice, computed by ray tracing on a
hexagonal tessellation of the floor, direct **and** diffuse sun.

!!! warning "This is not an LM-83 sDA"
    These columns are **irradiance aggregates at given instants**, not the
    share of the floor above 300 lux for 50 % of the occupied hours. Two
    consequences, to be written in black and white in any publication:

    1. calibrating on these columns bounds **these columns**, not an sDA;
    2. the indicator `Literal["sDA", …]` of `archlux.types` must then be read
       as the **label of the learned target**, not as the IES metric.

## Ingestion pipeline

1. Download from Zenodo (no account required, files of the order of a GB).
2. Rebuild the `Plan`s: room WKT `POLYGON` → bounding rectangles or
   rectilinear decomposition (`geom.rectilinear.decompose`); opening WKT
   → `Opening(wall_id=..., s=..., relative_width=...)` by projection onto the closest
   load-bearing wall — **never absolute coordinates**
   (`ARCHITECTURE.md` §10).
3. Deduplicate: `data.dedup`, Hausdorff distance \(0{,}02\,\mathrm{m}\).
4. **Only then** split (`data.splits`). Never the other way round: a duplicate
   straddling training and calibration silently falsifies the conformal
   coverage.
5. `scripts/prepare_data.py` writes the three directories.

## Cite

> Standfest, M. *et al.* (2022–2023). *Swiss Dwellings: A large dataset of
> apartment models including aggregated geolocation-based simulation results
> covering viewshed, natural light, traffic noise, centrality and geometric
> analysis*. Zenodo. [doi:10.5281/zenodo.7070951](https://doi.org/10.5281/zenodo.7070951)

**See also:** [MSD](msd.md) (derived from this corpus),
[ground truth](ground-truth.md), [imputation](imputation.md).
