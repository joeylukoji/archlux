# Milestone 8: summary, legalizing **actually generated** plans

Summary of the three runs of `experiments/j8_generation.py`. The detailed tables are
in `j8_etoile.md`, `j8_plausible.md` and `j8_divers.md`, the individual measurements
in the CSV files with the same prefix. The **before / after** comparisons, plan by plan,
are in [`visuals/`](visuals/index.md).

## Protocol

**Generator.** HouseDiffusion (Shabani, Hosseini, Furukawa, *CVPR 2023*), official
weights `model250000.pt`, trained on RPLAN. **Vector** output: no image vectorization
stands between the model and the measurement.

**Sampling at 1000 steps, without respacing.** `gaussian_diffusion.py:270` only
enables the **discrete** denoising branch (the one that snaps corners to the grid, and
the central contribution of the paper) for `t < 32`. Subsampling the trajectory
short-circuits it and creates a misalignment that does not belong to the model:

| steps | median distance from a corner to its axis-aligned rectangle |
|--:|--:|
| 20 | 0.750 m |
| 80 | 0.188 m |
| 200 | **0.000 m** |
| 1000 | **0.000 m** |

At 1000 steps the generated rooms are **exactly** axis-aligned: no bounding-box
approximation enters what follows.

**Three sets, two axes of diversity.** HouseDiffusion reads an access graph, from which
the `door_mask` derives: two unconnected rooms pay no attention to each other. Neither
the program nor the topology is therefore neutral, and a single choice would prove
nothing.

| set | plans | programs | topologies |
|---|--:|---|---|
| *etoile* | 320 | 8, from 4 to 8 rooms | star: everything attaches to the living room |
| *plausible* | 320 | the same 8 | distribution corridor if there is one, living room otherwise |
| *divers* | 100 | **25, from 3 to 10 rooms** | **all 4**, in rotation |

The *divers* catalogue covers what the first two do not reach: the three-room studio,
programs without a living room or without a kitchen, the study, storage rooms, double
bathrooms, and up to ten rooms. Its four topologies are the star, the plausible graph,
the **chain** (enfilade, the fewest possible edges) and the **ring** (the closed chain,
the only one carrying a cycle). The topology rotates over the programs sorted by size,
so that it is tied to no size: 5.50 to 6.17 rooms on average depending on the topology.

None of them is a graph of the RPLAN test set, which is not freely available. These
figures therefore describe the model **under synthetic conditioning**, that is, the
real deployment regime, where a user asks for "two bedrooms, open kitchen", and not the
benchmark regime.

**Scale.** RPLAN coordinates have no unit. The factor is set so that the median
generated area equals that of an MSD apartment (79.0 m², measured on 1,200
apartments), so that the displacements of milestones 7 and 8 are comparable. No
validity rate depends on it: overlap and gap are scale invariant.

740 plans in all, root seed 17.

## What the generator produces

| | etoile | plausible | divers |
|---|--:|--:|--:|
| plans valid before correction | **0 / 320** | **0 / 320** | **0 / 100** |
| rooms overlapped per room | 0.80 | 1.60 | 1.00 |
| gap share of the envelope | 28.6 % | 24.7 % | 28.7 % |
| of which **interior** holes | 0.0 % | 0.0 % | 0.0 % |
| disjoint fragments of the union | **4** | **2** | **3** |
| cells of the implicit grid | **80** | 64 | 64 |

The access graph trades gaps for overlaps (it glues part of the archipelago back
together at the price of twice as many overlaps), but **none of the 740 generated plans
is valid**, under any of the three conditionings.

Strictly interior holes are zero: the "gap" is not a perforation, it is space
**between** islands of rooms. The number of fragments confirms it.

The decisive figure is the number of cells: 64 to 80 grid cells for 6 rooms. In a real
plan the rooms share their walls and this number stays small. Here almost no
coordinates coincide: the combinatorial structure that `geom.tiling` relies on is not
merely violated, it is **absent**.

For context: the MSD authors report that their own baseline produces rooms that
overlap **4.11 ± 2.25** others, and that "overall, the floor plans often look
infeasible". The failure mode measured here is therefore not an accident of this
particular model.

## Repair

Rate of plans **certified valid** after correction, 95 % Wilson intervals.

Regulation `min_width = 0.50 m`; see the next section, this choice is decisive.

| mode | budget | etoile (n=320) | plausible (n=320) | divers (n=100) |
|---|--:|--:|--:|--:|
| `legalize` alone | — | **0.0 %** [0.0–1.2] | **0.0 %** [0.0–1.2] | **0.0 %** [0.0–3.7] |
| `tiling=True` | 0 | 0.6 % [0.2–2.2] | 0.6 % [0.2–2.2] | 3.0 % [1.0–8.5] |
| `tiling=True` | 4 | 10.9 % [8.0–14.8] | 10.6 % [7.7–14.5] | 17.0 % [10.9–25.5] |
| `tiling=True` | 8 | 18.4 % [14.6–23.1] | 16.6 % [12.9–21.0] | 23.0 % [15.8–32.2] |
| `tiling=True` | 16 | **20.3 %** [16.3–25.1] | **17.8 %** [14.0–22.4] | **23.0 %** [15.8–32.2] |

Median displacement at budget 16: 43 %, 38 % and 43 % of the side of the plan. Median
of 0.8 to 3.6 ms per correction in every case.

**The three sets give the same order of magnitude** (20.3 %, 17.8 %, 23.0 %) although
they do not produce the same defects and the third one covers three times as many
programs and four topologies. This is what allows these rates to be read as a property
of the generator / legalizer pair, and not of the conditioning it was given.

## The floor on the width is not a compliance detail

Without a strictly positive floor, **the cheapest way to close a gap is to shrink a
room to zero**. The plan then comes out "valid" and certified (it exactly tiles its
outline) minus a room that the drawing no longer even shows. Counting rooms does not
detect it: a room crushed to 0 m stays in the count.

At budget 16, by threshold:

| `min_width` | etoile: valid / **intact** | plausible | divers | smallest side (etoile) |
|--:|--:|--:|--:|--:|
| **0.00 m** | 60.9 % / **19.1 %** | 59.7 % / **13.8 %** | 59.0 % / **20.0 %** | **0.000 m** |
| 0.25 m | 20.3 % / 19.1 % | 17.8 % / 13.8 % | 23.0 % / 20.0 % | 1.360 m |
| **0.50 m** *(nominal)* | 20.3 % / **20.3 %** | 17.8 % / **17.8 %** | 23.0 % / **23.0 %** | 1.360 m |
| 1.00 m | 20.3 % / 20.3 % | 17.8 % / 17.8 % | 23.0 % / 23.0 % | 1.360 m |
| 1.80 m *(regulatory)* | 20.3 % / 20.3 % | 17.8 % / 17.8 % | 22.0 % / 22.0 % | 1.800 m |

"Intact" = certified valid **and** no room under 50 cm.

Two readings follow.

**The rate is flat from 0.25 m to 1.80 m.** So this is not a matter of tuning a
threshold: it is binary. Either annihilation is allowed and one gets ~60 % of plans, two
thirds of them mutilated, or it is forbidden and one gets ~20 % of whole plans. Requiring
the regulatory width of 1.80 m costs nothing more than requiring 25 cm.

**Milestone 7 was right to set `min_width = 0`, milestone 8 was wrong to copy it.** On
MSD, a 1.80 m threshold broke 52 plans out of 60 that were **already valid**: the caution
was justified. Here, 0 / 740 generated plans are valid to begin with, so the threshold
cannot break anything, and its absence only opens a degenerate way out for the solver.

### `legalize` alone repairs exactly zero plans

This is not a poor performance, it is the prediction of `geom.tiling` verified on real
data. The separations of the polytope are **inequalities**: a plan with a gap is already
the closest point to itself, the L1 optimum leaves it as is, and the exact verification
rejects it. Where milestone 7 left 35.9 % success to the base mode (because a corrupted
plan still covers its outline), a generator output leaves none.

### The default budget is tuned on the wrong regime

`legalize` fixed `repair_budget` at 4, a value tuned on corrupted plans where the fault
is a wrong dimension and is absorbed in one step. Here the rate triples between 4 and
16, then saturates. The parameter is now exposed.

### What governs the rate: the size of the grid

It is **not** connectivity: plans in one piece are not repaired better (16.7 % at 1
fragment against 70.7 % at 4, on unbalanced counts). It is the number of rooms, through
the size of the grid:

| rooms | etoile | plausible | divers | median cells |
|--:|--:|--:|--:|--:|
| 3 | — | — | 66.7 % | 16 |
| 4 | 75.0 % | 75.0 % | 68.8 % | 30 |
| 5 | 77.5 % | 80.0 % | 65.0 % | 48 |
| 6 | 65.0 % | 60.0 % | 81.2 % | 72 |
| 7 | 48.3 % | 49.2 % | 50.0 % | 84 |
| 8 | 47.5 % | 35.0 % | 33.3 % | 118 |
| 9 | — | — | 25.0 % | 131 |
| 10 | — | — | *50.0 %* (n=4) | 181 |

The relation is monotone and has an explanation: when no edges coincide, the grid swells
as \\((2n-1)^2\\), whereas the bounded repair only fixes a bounded number of cells.

The *divers* catalogue extends the curve at both ends: the three-room studio rises to
66.7 %, the nine-room plan falls to 25 %. The ten-room cell holds only four plans: it is
shown so as to hide nothing, not to be read.

### The graph topology matters too, but this is not yet established

On the only set where the four topologies coexist:

| topology | n | repaired | 95 % CI | median overlap | median fragments |
|---|--:|--:|:--:|--:|--:|
| `plausible` | 24 | 75.0 % | [55.1–88.0] | 0.93 | 3 |
| `etoile` | 28 | 64.3 % | [45.8–79.3] | 0.93 | 4 |
| `anneau` | 24 | 54.2 % | [35.1–72.1] | 1.00 | 3 |
| `chaine` | 24 | 41.7 % | [24.5–61.2] | **1.42** | 2 |

The order follows the number of edges of the graph, and the mechanism is clear: only
connected rooms attract each other's attention, so the poorer the graph, the more the
rooms overlap; the chain, which has the fewest edges, does have the worst overlap rate
(1.42 against 0.93).

**This is not conclusive**: at n = 24 per cell, the intervals of `chaine` and
`plausible` nearly touch without clearly separating. It is however not a size effect:
`chaine` carries the **smallest** programs (5.67 rooms on average against 6.17 for
`anneau`) and gets the **worst** rate.

### The remaining failures are named, and 13 are proven

At budget 16, 112 to 116 grid refusals remain (the bounded repair is not enough) and
**13 certified infeasibilities**. These are not crashes: the Farkas certificate is a
sparse vector with 2 to 3 non-zero components out of 45, and the origins name the
minimal conflict, for example `separation horizontale p000|p003 ; contour
droit p000`. At a large budget, the repaired grid ends up contradicting the
separations derived from `deduce_order`, which also explains the observed saturation.

## What this milestone establishes, and what it does not claim

It establishes that the tiling constraint is **necessary**: out of 740 plans generated
under three conditionings, **none** is recoverable without it, about one in five is
with it. The gap is not a tuning effect.

It also establishes that it is **not sufficient**, in two ways.

First, the median displacement reaches 38 to 43 % of the side of the plan: what comes
out is a valid plan *in the neighbourhood* of the generated plan, not the generated plan
corrected. When the input is this far from any exact tiling, "the closest valid plan" is
not close; the L1 projection does its job, it is the input that is pathological. The
point of comparison is budget 0, where the rare plans that are already almost consistent
move by only 18 %.

Second, **four plans out of five cannot be repaired at all** while preserving the
program. The ~60 % figure obtained without a floor on the width is not one: it counts as
successes plans that lost a room.

The useful conclusion is therefore not "61 % are repaired", nor even "20 % are
repaired", but: **after-the-fact legalization does not replace a generator that respects
the tiling condition**. It guarantees validity and proves it; it guarantees neither
resemblance nor the survival of the program, and it has to be asked for them explicitly.
The constraint belongs *inside* the generator: something this repository makes it
possible to quantify, not something it provides.

This confirms milestone 7 as the main table: it is the one that isolates the repair
capacity in the regime where repairing makes sense, with a known, attributable fault.

## Reproduce

Sampling lives **outside the repository**: HouseDiffusion is under GPL v3 and forbids
commercial use, archlux is under Apache-2.0 and does not import it. The boundary
between the two is the JSONL file.

```bash
# stage 1, outside the repository (GPL)
python vendor/j8_generer.py plans.jsonl --n 40 --pas 1000 --graphe plausible
python vendor/j8_generer.py divers.jsonl --n 4  --pas 1000 --catalogue divers

# stage 2, in the repository (Apache-2.0): tables, then before/after sheets
python experiments/j8_generation.py plans.jsonl 999 plausible
python experiments/j8_visuals.py    plans.jsonl plausible 8
```

The sampling batch is **heterogeneous** (one program per element) because the cost is
dominated by the 1000 sequential steps and not by the batch size: the whole *divers*
catalogue fits in one four-minute pass rather than twenty-five passes of three.
