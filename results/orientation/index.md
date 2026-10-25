# Milestone 9: variants by solar azimuth

> **Label corrected (review).** The scores below were labelled "sDA". They are the value of `AnalyticSurrogate(target_indicator="sDA")`, a closed-form score in m²-weighted points, **not** an LM-83 sDA (percent of floor area). The gains are **predicted** by that surrogate. These pages predate the current code; the re-run, with the closed-form reference and a sweep, is `results/j9_review.md`.


Displacement budget 3.0 m (infinity norm around the L1 point), `min_width = 0.50 m`.

**The optimized objective is not real daylight**: see the header of `experiments/j9_orientation.py`. What is guaranteed is geometric.

| plan | rooms | azimuth of the best surrogate score | predicted gain | displacement | smallest side | valid variants |
|---|--:|--:|--:|--:|--:|--:|
| [`hd0012`](hd0012.md) | 4 | 45° | +12 % | 3.00 m | 0.50 m | 8 / 8 |
| [`hd0013`](hd0013.md) | 4 | 135° | +21 % | 3.00 m | 1.25 m | 8 / 8 |
| [`hd0016`](hd0016.md) | 4 | 45° | +16 % | 3.00 m | 0.50 m | 8 / 8 |
| [`hd0018`](hd0018.md) | 4 | 45° | +23 % | 3.00 m | 0.50 m | 8 / 8 |
| [`hd0022`](hd0022.md) | 4 | 90° | +13 % | 2.46 m | 0.50 m | 8 / 8 |
| [`hd0026`](hd0026.md) | 4 | 45° | +9 % | 3.00 m | 0.50 m | 8 / 8 |
