# Milestone 7: where is the variance of the irradiance?

Swiss Dwellings v3.0.0 corpus, 367,466 rooms, target `sun_201803211200_mean`.
Total variance 17.89.

| fixed effect | groups | R2 |
|---|--:|--:|
| building identity | 3,171 | **0.026** |
| building x floor | 13,688 | 0.068 |
| apartment identity | 44,888 | **0.077** |
| floor number alone | — | 0.004 |

## Reading

**92 % of the variance lies within apartments**, that is, between rooms. The identity of
the building, which carries the urban mask, the climate and the sun position, explains
only **2.6 %**.

Two consequences, and the second one is structural.

**The urban mask is not the missing factor.** The hypothesis was natural and it is
wrong: a building effect caps at 2.6 %. The climate normals confirm it another way:
`climate_snorm_year` correlates at r = -0.06 with the target, `climate_snorm_march` at
r = +0.05. `sun_*` is a geometric ray tracing for a given sun position, not a weather
quantity.

**Aggregating by apartment destroys the signal.** The `Surrogate` protocol returns **one
scalar per plan**; daylight is a **per-room** quantity. Predicting an apartment mean
amounts to predicting a quantity whose variance is only 7.7 % of that of the phenomenon,
the rest being smoothed out by the aggregation. This explains the `R2 ~ 0` of
`j7_sd_labels.md` far more than the poverty of the inputs.

## What it implies

The granularity of the protocol is at stake, not only its vocabulary. A useful surrogate
would return a **vector** (one value per room) and Frank-Wolfe would optimize an explicit
scalarization of those values (weighted mean, minimum, share above a threshold). This is
also what would make an sDA-type indicator representable: it is defined per room, not
per dwelling.

It is a deeper contract change than adding `Glazing`, and it touches `solve` as much as
`light`.
