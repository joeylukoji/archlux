# Release 1.0.0 — checklist

This document prepares the software release. **It does not replace** the
admissibility conditions of the journals (public history, third-party use).

## Ready in the repository

| Deliverable | Status |
|---|---|
| Version `1.0.0` (`_version.py`, single source) | **no**: `0.10.0.dev0`, 1.0.0 postponed (PLAN.md phase 5) |
| Frozen API + `test_api_publique_stable` | test present; freeze postponed (English renaming, ADR 0001) |
| `CHANGELOG.md` section `1.0.0` | section removed (never published) |
| `CITATION.cff` | yes (URL / DOI to finalize) |
| Apache-2.0 licence (`LICENSE` file) | yes (added in phase 0) |
| MkDocs docs (`mkdocs build --strict`) | yes |
| `CONTRIBUTING.md` | yes |
| CI tests (dependencies, torch out of the core) | yes |

## To do outside the code (maintainers)

1. Replace `ORG/archlux` in `CITATION.cff`, `README`, `docs/contributing.md`
   with the real public URL.
2. Tag `v1.0.0` and archive (Zenodo / Software Heritage) → DOI in
   `CITATION.cff`.
3. Publish the distribution on the package index (`twine` / Trusted Publishing).
4. Attach to the public repository: surrogate weights, **calibration set**,
   `splits/`, raw benchmark results.
5. Wait for **≥ 6 months** of spread-out public history and **at least one documented
   third-party use** before a software-journal submission
   (`MILESTONE-6.md` §7).

## **Scientific** publication — what is still missing

This page covers the *software* release. A peer-reviewed paper
asks for something else, and the repository is not there.

| Requirement | Status | Where |
|---|---|---|
| Method formulated, sourced, derived | ✅ | `docs/formulas/` (17 located references) |
| Verifiable, typed, tested implementation | ✅ | clean `mypy --strict`, 89 % coverage |
| Performance budgets met | ✅ | `benchmarks/`, `ARCHITECTURE.md` §9 |
| **Measured daylight labels** | ❌ | closed form only — [ground truth](data/ground-truth.md) |
| **Real corpus loaded** | ❌ | WKT loader to write (`data/loaders.py`) |
| **Baseline: 3 public generative models** | ❌ | `MILESTONE-2.md` §8; never built: `j2_brut.csv` contained 2 hand-made plans (removed); review [`j2`](revues/j2.md) |
| **Conformal coverage measured on a real corpus** | ❌ | `n = 18` in synthetic calibration |
| Ablation study (tokens, window imputation, active vs random) | ⚠️ | scripts present, results at toy scale |
| Comparison with the state of the art | ❌ | none |

**Honest reading:** milestones 1–6 show that an *architecture* holds — two
guarantees separated by construction, one solver for two objectives, a certificate
that refuses to conclude when exchangeability fails. It is a software-engineering
and design result, defensible as such (tool paper / JOSS-like, or the
"method" section of a broader paper).

It is not yet an experimental result: no physical quantity has been
measured, no public generator has been repaired, no baseline has been beaten.

## 1.x API contract

Any removal or renaming of a symbol of `archlux.__all__` is a
**version 2.0**. Non-breaking additions stay in `1.x`.

A change of behaviour of `lmo` or `certify` → **major** version
(reproducibility of the certificates).

## Cite

```bibtex
@software{archlux100,
  title   = {archlux: geometric legalization of generated floor plans
             with conformally bounded daylight surrogates},
  version = {1.0.0},
  year    = {2026},
  url     = {https://github.com/ORG/archlux},
  license = {Apache-2.0}
}
```

Prefer the Zenodo DOI once the archive is created.
