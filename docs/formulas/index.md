# Formulas of milestones 2 and 3

This folder is the **formulary**: every result used in the code is stated,
derived, sourced and tied to a function here. A researcher should be able to redo the
computation on paper without opening the implementation.

The `concepts/` pages explain *why* the architecture is the way it is.
The `formulas/` pages explain *which equality* is coded, and where it comes from.

## Map from milestone 2 to pages

| Step | Module | Page | Guarantee |
|---|---|---|---|
| Relative order | `geom.graph` | [Order and graph](relative-order.md) | exact |
| Polytope | `geom.polytope` | [Linear separations](separated-polytope.md) | exact |
| L1 objective | `geom.polytope`, `api` | [L1 epigraph](l1-epigraph.md) | exact (reformulation) |
| Areas | `lmo.cuts` | [Area cuts](area-cuts.md) | exact (convex support) |
| LP oracle | `lmo.solver` | [Simplex, duals, Farkas](farkas.md) | exact (LP) |
| Proof | `certify.proof` | [Exact verification](exact-proof.md) | exact (inspection) |
| Chain | `api.legalize` | [Pipeline](pipeline.md) | exact on output |
| Orientation | `orient.circular` | [Circular statistics](circular.md) | exact (trigonometry) |
| Surrogate M3 | `light.analytic` | [Analytic surrogate](analytic-surrogate.md) | **no guarantee** |
| Split-flux M4 | `light.split_flux` | [Daylight factor](split-flux.md) | **no guarantee** (not an sDA) |
| Rectilinear M6 | `geom.rectilinear` | [L decomposition](rectilinear.md) | exact (partition + merges) |
| Active M6 | `active` | [Active learning](active-learning.md) | simulation budget |
| Export M6 | `export` | [IFC / DXF / Wilson](bim-export.md) | exact (pathologies); Wilson |
| Benchmark M6 | `bench` | [Benchmark](benchmark.md) | trace + statistics |
| Tokens M4 | `light.tokens` | [Tokens](tokens.md) | continuous (anti-image) |
| Learned surrogate M4 | `light.base` | — (`numpy` perceptron) | **no guarantee**; target = analytic residual |
| Gradient M4 | `light.validation` | [Gradient validation](gradient-validation.md) | sign agreement |
| Frank-Wolfe | `solve.frank_wolfe` | [Frank-Wolfe](frank-wolfe.md) | exact iterates; optimality gap |
| Statistics M5 | `uq.conformal` | [Conformal prediction](statistics.md) | probabilistic |

## How to read a page

Every page has the same structure:

1. **Statement** — the formula, alone.
2. **Assumptions** — what must be true for the equality to hold.
3. **Derivation** — enough steps to rebuild it.
4. **Code** — function and files.
5. **Use cases** — when to apply it, when it is **wrong**.
6. **Source** — edition, section or theorem, DOI if the article has one.

The sources are gathered in [the bibliography](sources.md). A citation without a
location (chapter, theorem, DOI) is not accepted.

## Exact vs probabilistic

At milestone 2, the geometric and linear optimization formulas are **exact**.
At milestone 3, the Frank-Wolfe iterates stay in the polytope (exact guarantee);
the score of the analytic surrogate **has no coverage at all**. At milestone 5,
conformal prediction bounds the frozen oracle: see [statistics](statistics.md).
This is not a geometric proof.

!!! warning "What \"the frozen oracle\" means"
    `SplitFluxOracle` is a **closed form**, not a measurement nor a ray tracer.
    A coverage computed against it is a coverage *on that formula*. No page in
    this folder claims otherwise, and [ground truth](../data/ground-truth.md)
    says where to find real labels.
