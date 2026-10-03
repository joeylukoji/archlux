# Synthetic corpus

**Code:** `data.synthetic.generate_corpus`.

2×2 tilings in a 12 m × 9 m envelope, identifiers `syn-0000` … `syn-0089`.
The seed is mandatory. It serves as the CI stand-in for the real-estate corpora that
cannot be redistributed.

Frozen split: `splits/v1/{train,calibration,test}.txt` (54 / 18 / 18).
`syn-0053` repeats the geometry of `syn-0000` (same train split) for the
cross-boundary deduplication test.

This is **not** a measured sDA. The score comes from `SplitFluxOracle`
(CIBSE analytic + BRE split-flux; Radiance off the critical path).
