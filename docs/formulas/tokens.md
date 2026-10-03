# Tokens of a plan

**Code:** `light.tokens.plan_to_tokens`, `vector_to_tokens`, `permute_rooms`.

## Statement

A plan is not an image. It becomes a **set** of tokens
\(\{\phi_1,\ldots,\phi_N\}\subset\mathbb{R}^{d}\), \(d=32\)
(`TOKEN_DIM`), of **two families**, in this order: the rooms, then the glazing.

\[
N = \underbrace{n_{\text{rooms}}}_{\text{always}}
  + \underbrace{n_{\text{attached glazing}}}_{\text{0 if the plan has neither walls nor openings}}
\]

A window is **never copied** onto each room: it is its own token.

## Layout of the 32 components

| Indices | **Room** token | **Glazing** token |
|---:|---|---|
| `0:4` | \((x,y,w,h)\), metres | 0 |
| `4:7` | \(\bigl(wh,\;2(w+h),\;\tfrac{4wh}{4(w+h)^2}\bigr)\) — area, perimeter, compactness | 0 |
| `7:14` | one-hot of the type over 6 categories + 1 "unknown" slot | 0 |
| `14:20` | \(\phi(\theta_{\text{building}})\), harmonics 1–3 | same |
| `20` | \(n_{\text{rooms}}\) | same |
| `21` | \(\sum_j w_j h_j\) | same |
| `22:24` | 0 | \(\phi(\theta_{\text{wall}})\), harmonic 1 |
| `24:27` | 0 | \((s,\ \text{relative\_width},\ \text{head\_height})\) |
| `27` | 0 | **1.0 — "this is glazing" flag** |
| `28` | 0 | sill height |
| `29:32` | 0 (reserved) | 0 (reserved) |

\(\phi(\theta)\) are the [circular harmonics](circular.md) — never the raw
degree. \(\theta_{\text{wall}}=\operatorname{atan2}(b_y-a_y,\;b_x-a_x)\) is the azimuth of the
wall carrying the window, in degrees.

Compactness is \(1/4\) for a square and tends to \(0\) for a degenerate
rectangle; it is not the Polsby–Popper index \(4\pi A/P^2\), but the same
quantity up to a factor \(\pi\).

## The padding mask

`plan_to_tokens` returns the pair \((\text{tokens }[N,d],\ \text{mask }[N])\), where
`mask[i]` is **true if token i is padding** — the PyTorch
`src_key_padding_mask` convention, not the reverse. On a single plan the mask is entirely
false; it only becomes useful in a batch of plans of different sizes.

## Assumptions

- Coordinates in metres, \((x,y,w,h)\) per-room contract, **same order as
  `Polytope.index`** — this is what makes the surrogate's gradient directly
  addable to the decision vector.
- A displacement of \(2\,\mathrm{cm}\) **must** change \(\phi\): this is the anti-image
  test. On a raster at 100 px/m, this displacement changes no pixel, the
  gradient is zero almost everywhere, and the optimizer is blind
  (`ARCHITECTURE.md` §10, first anti-pattern).
- Every set statistic (mean, sum) is **permutation invariant** over
  the rooms: `permute_rooms` must not change the score. This is what
  `tests/unit/test_tokens.py` tests.
- An opening whose `wall_id` matches no wall of the plan is
  **silently ignored** (`plan_to_tokens`). This is a choice: an incomplete corpus
  must not bring the encoding down. The flip side is that a wall/window
  matching error is not reported here — it is reported at
  devectorization.

## Use cases

| Do | Do not |
|---|---|
| Encode from `Plan` when walls and glazing exist | Believe that `vector_to_tokens` encodes glazing: it only sees \((x,y,w,h)\) and forces the type `"living_room"` |
| Check permutation invariance | Sort the tokens by position (that would be an implicit order) |
| Add a component at the end of the vector | Reindex `0:22` — the frozen `npz` weights would become wrong without anything reporting it |

!!! warning "The shipped corpus does not exercise the glazing tokens"
    `data.synthetic.generate_corpus` produces plans with `walls=()` and
    `openings=()`. Columns `22:29` are therefore **identically zero** there, and
    `SplitFluxOracle` uses its default WWR (0.30) whatever the
    fenestration. See [ground truth](../data/ground-truth.md).

## Source

Architecture decision: `ARCHITECTURE.md` §10; `MILESTONE-4.md` §4 (order of
the families). Harmonics: Mardia & Jupp (2000), see [circular](circular.md).
[Why not an image](../concepts/why-not-an-image.md).
