# Before / after comparisons: milestone 8

This folder exists because a rate does not say what a repair looks like. The two
figures of milestone 8, **plans made valid** and **median displacement of 43 % of the
side of the plan**, are both correct and suggest opposite things. Here we look.

> **This folder has already served.** Looking at these sheets is how rooms shrunk to
> zero thickness by the correction were spotted: a "repaired" plan, certified valid,
> minus a room. No table showed it: the room count stayed right. The regulation now
> sets `min_width = 0.50 m`, and the announced repair rate went from ~60 % to ~20 %. See
> [`../j8_generation.md`](../j8_generation.md), section on the width floor.

## How to read a sheet

Each plan has two files in the sub-folder of its **outcome**:

- `<plan>.svg`: both states **at the same scale**. One scale per panel would give a
  shrunk plan the look of an intact one; `export.svg.compare` forbids it by
  construction.
- `<plan>.md`: the metrics: geometric diagnostic before (`geom.diagnostic`),
  violations found by the exact verification (`certify.proof`), then verdict and
  displacement after correction.

Drawing conventions:

| element | reading |
|---|---|
| red dashes | the **target outline**, drawn even if no room reaches it |
| semi-transparent fills | the rooms: an **overlap** shows as a denser area |
| light background inside the dashes | a **gap**: uncovered area |
| a single panel | no plan was produced; redrawing the input on the right would read as "nothing changed" |

## The three outcomes

Eight plans per outcome and per conditioning, **failures included**: a folder that
showed only what works would be useless.

| outcome | what it means |
|---|---|
| `repaired` | plan certified valid: look at the displacement before concluding |
| `unrecoverable grid` | the bounded repair does not make the partition consistent; `deduce_grid` refuses and names the faulty cells |
| `proven infeasible` | the system is **proven** to have no solution, with a Farkas certificate: 2 to 3 conflicting constraints out of 45 |

## The three sets

HouseDiffusion reads an access graph from which its `door_mask` derives: neither the
program nor the topology is neutral, and measuring on a single choice would prove
nothing.

| set | plans | programs | topologies |
|---|--:|---|---|
| [`etoile/`](etoile/index.md) | 320 | 8 programs, 4 to 8 rooms | star: everything attaches to the living room, the conditioning taken as is from `A-AI/services/ai/app/housediff.py` |
| [`plausible/`](plausible/index.md) | 320 | the same 8 | distribution corridor if there is one, kitchen and dining room next to the living room |
| [`divers/`](divers/index.md) | 100 | **25 programs, 3 to 10 rooms**: studio, no living room, study, storage, several bathrooms | **all 4**: star, plausible, chain, ring, in rotation |

The 100 sheets of `divers/` are **all** there, not a sample: 23 repaired,
38 unrecoverable grids, 39 proven infeasibilities.

The three sets give the same order of magnitude (20.3 %, 17.8 %, 23.0 %) with different
defects: the star fragments, the chain overlaps. See
[`../j8_generation.md`](../j8_generation.md) for the tables and the protocol.
