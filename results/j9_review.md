# B9 reviewed: variants by azimuth against the closed-form reference

Inputs: the six B9 plans **rebuilt from the published sheets** (`experiments/j9_inputs.py`, about 1 mm; the original `j8_plans_divers.jsonl` is not in the repository). Surrogate optimized: `AnalyticSurrogate(target_indicator="sDA")`, the analytic closed form, **not** the trained network. Reference: `SplitFluxOracle`, a frozen closed form, **not a physical simulation**. The score the old pages call "sDA" is the surrogate's value for that label (m²-weighted points), not an LM-83 sDA; it is called `surrogate_score` here. Seed 17. Intervals resample whole plans (6 clusters), since the 8 azimuths of a plan are not independent.

## 1. The published variants, re-scored

48 variants rebuilt from `results/orientation/*.svg`. Re-scoring them with today's surrogate gives back the published **gains** to within 0.02 percentage points (checks the rebuild). The raw scores themselves differ from the published ones by a factor that depends on the azimuth only: the score's scale changed between the two code versions, its ratios did not.

- median **predicted** gain: +17.2 % (published: +17.2 %)
- median **reference** gain on the same plans: +9.8 %
- variants with a room below 4 m²: 15 / 48

## 2. Re-run on the current code (budget 3 m, no penalty, no minimum area)

- variants: 48 / 48, exact proof 48, independent validator 48
- median predicted gain +17.2 % [+13.5 ; +22.3]; median reference gain +9.8 % [+5.0 ; +14.9]
- sign of the predicted gain confirmed by the reference: 46 / 48; **this is partly by construction**: `SplitFluxOracle` is `AnalyticSurrogate` plus a split-flux daylight-factor x area term, so the reference contains the optimized score. The independent part, the DF term alone, changes by a median +0.4 % and decreases on 21 / 48 variants
- variants at the budget (max wall shift = 3 m): 34 / 48, 95 % CI by plan [0.54 ; 0.88] (published: 36 / 48)
- Frank-Wolfe stops: converged 22, line_search_failed 26
- out of the inputs' envelope: 33 / 48
- reproduces `legalize(..., objective=, budget=)` exactly: 48 / 48

## 3. Sweep: budget x proximity penalty x minimum area

"saturated": the largest wall shift equals the budget. "rooms < 4 m²": variants with at least one such room. Gains against the legalized plan, so with a minimum area they include the L1 repair that enforces it (run with tiling, which the generated plans need). In those cells the Frank-Wolfe domain here leaves out the tiling grid that `legalize(..., tiling=True)` adds: 27 variants differ from `legalize`'s own (column `matches_legalize`); every variant listed is proven valid and accepted by the independent validator.

| budget (m) | penalty λ | min area | ok / n | median predicted gain [95 % CI by plan] | median reference gain | sign agrees | saturated | rooms < 4 m² | median max wall shift (m) | FW converged |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.5 | 0 | - | 48 / 48 | +3.1 % [+2.4 ; +4.3] | +2.3 % | 46 / 48 | 48 / 48 | 11 / 48 | 0.50 | 43 / 48 |
| 0.5 | 0 | 4.0 | 40 / 48 | +2.8 % [+2.0 ; +4.1] | +2.2 % | 38 / 40 | 40 / 40 | 0 / 40 | 0.50 | 35 / 40 |
| 0.5 | 0.1 | - | 48 / 48 | +3.1 % [+2.4 ; +4.3] | +2.3 % | 47 / 48 | 43 / 48 | 12 / 48 | 0.50 | 37 / 48 |
| 0.5 | 0.1 | 4.0 | 40 / 48 | +2.8 % [+1.9 ; +4.1] | +2.2 % | 38 / 40 | 35 / 40 | 0 / 40 | 0.50 | 28 / 40 |
| 0.5 | 1 | - | 48 / 48 | +2.7 % [+1.5 ; +4.2] | +1.9 % | 47 / 48 | 24 / 48 | 14 / 48 | 0.49 | 42 / 48 |
| 0.5 | 1 | 4.0 | 40 / 48 | +2.3 % [+1.5 ; +4.1] | +1.7 % | 38 / 40 | 22 / 40 | 0 / 40 | 0.50 | 31 / 40 |
| 1 | 0 | - | 48 / 48 | +6.1 % [+4.6 ; +8.4] | +4.2 % | 45 / 48 | 45 / 48 | 9 / 48 | 1.00 | 33 / 48 |
| 1 | 0 | 4.0 | 48 / 48 | +5.5 % [+4.6 ; +7.7] | +4.2 % | 45 / 48 | 45 / 48 | 0 / 48 | 1.00 | 33 / 48 |
| 1 | 0.1 | - | 48 / 48 | +6.1 % [+4.3 ; +8.4] | +4.2 % | 46 / 48 | 37 / 48 | 10 / 48 | 1.00 | 29 / 48 |
| 1 | 0.1 | 4.0 | 48 / 48 | +5.5 % [+4.4 ; +7.7] | +4.2 % | 46 / 48 | 37 / 48 | 0 / 48 | 1.00 | 27 / 48 |
| 1 | 1 | - | 48 / 48 | +3.8 % [+2.1 ; +6.9] | +2.5 % | 47 / 48 | 17 / 48 | 14 / 48 | 0.58 | 22 / 48 |
| 1 | 1 | 4.0 | 48 / 48 | +4.5 % [+2.5 ; +6.9] | +3.0 % | 46 / 48 | 21 / 48 | 0 / 48 | 0.89 | 18 / 48 |
| 2 | 0 | - | 48 / 48 | +11.9 % [+8.9 ; +16.2] | +7.3 % | 46 / 48 | 39 / 48 | 8 / 48 | 2.00 | 27 / 48 |
| 2 | 0 | 4.0 | 48 / 48 | +11.9 % [+8.9 ; +15.3] | +7.3 % | 47 / 48 | 38 / 48 | 0 / 48 | 2.00 | 26 / 48 |
| 2 | 0.1 | - | 48 / 48 | +11.9 % [+6.5 ; +16.1] | +6.9 % | 46 / 48 | 28 / 48 | 11 / 48 | 2.00 | 21 / 48 |
| 2 | 0.1 | 4.0 | 48 / 48 | +11.8 % [+6.9 ; +15.8] | +6.9 % | 46 / 48 | 30 / 48 | 0 / 48 | 2.00 | 19 / 48 |
| 2 | 1 | - | 48 / 48 | +3.8 % [+2.2 ; +9.2] | +2.8 % | 47 / 48 | 10 / 48 | 14 / 48 | 0.60 | 6 / 48 |
| 2 | 1 | 4.0 | 48 / 48 | +4.9 % [+2.5 ; +9.2] | +3.2 % | 46 / 48 | 10 / 48 | 0 / 48 | 0.91 | 4 / 48 |
| 3 | 0 | - | 48 / 48 | +17.2 % [+13.5 ; +22.3] | +9.8 % | 46 / 48 | 34 / 48 | 15 / 48 | 3.00 | 22 / 48 |
| 3 | 0 | 4.0 | 48 / 48 | +17.0 % [+13.5 ; +21.1] | +10.2 % | 46 / 48 | 31 / 48 | 0 / 48 | 3.00 | 19 / 48 |
| 3 | 0.1 | - | 48 / 48 | +16.1 % [+7.5 ; +22.3] | +8.5 % | 46 / 48 | 21 / 48 | 10 / 48 | 2.75 | 16 / 48 |
| 3 | 0.1 | 4.0 | 48 / 48 | +15.8 % [+8.0 ; +22.3] | +9.8 % | 47 / 48 | 20 / 48 | 0 / 48 | 2.75 | 13 / 48 |
| 3 | 1 | - | 48 / 48 | +3.8 % [+2.2 ; +9.3] | +2.8 % | 47 / 48 | 0 / 48 | 14 / 48 | 0.59 | 0 / 48 |
| 3 | 1 | 4.0 | 48 / 48 | +5.2 % [+2.5 ; +9.7] | +3.5 % | 46 / 48 | 0 / 48 | 0 / 48 | 0.97 | 0 / 48 |

## 4. Why B9 reports +17.2 % and the ablation +1.6 %

Same surrogate (`AnalyticSurrogate`, label sDA), same reference, same Frank-Wolfe, budget 3 m. Only the plans and the rules change:

The reference column contains the predicted score (see section 2); it is shown for comparison with `results/ablations.md`, which uses the same reference.

| plans | rules | n | median predicted gain | median reference gain |
|---|---|--:|--:|--:|
| B9 plans | B9 rules (no structure, no minimum area, 0.5 m) | 48 | +17.2 % | +9.8 % |
| B9 plans | ablation rules (80 % minimum areas, 1.0 m) | 48 | +9.7 % | +7.2 % |
| synthetic 2x2 plans (ablation) | ablation rules (wall, 80 % areas, 1.0 m) | 240 | +1.9 % | +0.9 % |
| synthetic 2x2 plans (ablation) | B9 rules (no structure, no minimum area, 0.5 m) | 240 | +12.4 % | +4.0 % |

## 5. Timing

160 runs (20 plans x 8 azimuths), raw rows in `j9_timing_raw.csv`, machine in `j9_review_manifest.json`. These are not necessarily the 20 plans of the article, which did not name them. Outcome of the L1 pass without tiling: GapNeedsTiling 160 (a refusal is timed like a success: on generated plans the first row times how long the L1 pass takes to refuse).

| stage | n | median (ms) | p90 (ms) | max (ms) |
|---|--:|--:|--:|--:|
| legalization (L1 LP) | 160 | 2.9 | 3.8 | 5.1 |
| legalization + tiling | 160 | 4.8 | 6.4 | 12.8 |
| Frank-Wolfe, r = 3 m | 160 | 10.7 | 15.6 | 51.1 |

Frank-Wolfe variants accepted by the independent validator: 160 / 160.
