# DOCUMENTATION — conventions and obligations

> Context for coding agents. **To be read with `ARCHITECTURE.md`.**
> Documentation is part of the definition of "done". An undocumented public function
> is an unfinished function.

---

## 1. Principle

**Documentation is written in the reverse order of desire.**

| Priority | Level | Why |
|:--:|---|---|
| **1** | **Example gallery** | First driver of adoption. A user looks at an example, thinks "that is what I need", installs |
| 2 | Tutorials | Guided paths for the 3–4 main uses |
| 3 | API reference | Necessary, but nobody opens it to discover a tool |

The natural desire is to write the reference first because it is generated automatically. **It is the least useful order.**

---

## 2. Structure

```
docs/
├── index.md                 # the positioning sentence + 5-line example
├── installation.md
├── gallery/                 # PRIORITY 1 — one file per example, self-contained
│   ├── 01-repair-a-plan.md
│   ├── 02-compare-two-methods.md
│   ├── 03-detect-infeasibility.md
│   ├── 04-read-a-certificate.md
│   └── 05-dual-diagnostics.md
├── tutorials/
│   ├── getting-started.md
│   ├── performance-legalization.md
│   └── calibrate-a-surrogate.md
├── concepts/                # the WHY, not the how
│   ├── two-guarantees.md
│   ├── polytope.md
│   ├── shared-oracle.md
│   └── conformal-prediction.md
├── formulas/                # statement, derivation, source, use case (milestone 2+)
│   ├── index.md
│   └── sources.md
├── reference/               # generated from the docstrings
└── limitations.md           # what the system does NOT do
```

**`concepts/two-guarantees.md` is the most important page of the site.** It explains
that a certificate carries a proof and a prediction, of logically different kinds.
Everything else follows from it.

**`limitations.md` is mandatory, not optional.** A system that produces regulatory
numbers must say explicitly what it does not check.

---

### Bilingual site

The site is published in English (default) and French with `mkdocs-static-i18n`, suffix
structure. **English is the reference**: `docs/x/page.md` is the page,
`docs/x/page.fr.md` its French translation. Translated: home, installation, gallery,
tutorials, concepts, formulas, data, release, limitations, contributing and the JSON
schema; the API reference, glossary, specification, ADRs and reviews are English only
(the French site falls back to them).

- **Code is not translated.** Every fenced block of `page.fr.md` is the block of
  `page.md`, verbatim and in the same order; `tests/docs/test_examples.py` enforces it,
  and also fails if a page of the translated list loses its `.fr.md`.
- **Links name the English file** (`../formulas/tiling.md`), never a `.fr.md`: the
  plugin localizes them.
- **Update both in the same commit.** A change to the facts, numbers or formulas of an
  English page is carried into its `.fr.md` in the same commit.
- `.fr.md` files are French by design: the language guard (`tests/test_language.py`)
  never scans them.

## 3. Docstrings — the mandatory template

**NumPy** style. Every public function must have the sections marked ✱.

```python
def legalize(plan: Plan, ctx: Context, *, objective=None,
             budget: float | None = None) -> Plan:
    """Repair a plan towards the closest valid plan.                 ✱ 1-line summary

    With ``objective=None``, minimizes the displacement of the walls ✱ description
    (classic legalization). With an objective, maximizes it
    under the validity and displacement-budget constraints.

    Parameters                                                       ✱
    ----------
    plan : Plan
        Proposed plan, possibly invalid.
    ctx : Context
        Load-bearing structure, orientation, outline, regulation.
    objective : Surrogate | None, optional
        Objective to maximize. ``None`` = geometric proximity.
    budget : float | None, optional
        Maximum allowed displacement, in metres.

    Returns                                                          ✱
    -------
    Plan
        Valid plan carrying its ``certificate``.

    Raises                                                           ✱
    ------
    Infeasible
        The program does not fit in the envelope. The exception carries
        ``certificate``: the conflicting constraints.
    InvariantViolation
        The solver produced an invalid output (internal bug).

    Guarantees                                                       ✱ PROJECT-SPECIFIC
    ----------
    - Geometric: **exact**. ``result.certificate.geometry.valid``
      is checked independently of the solver before returning.
    - Performance: **probabilistic** if ``objective`` is given.
      Coverage ≥ 1−α, under the assumption of exchangeability with the
      calibration set.

    Complexity                                                       ✱ PROJECT-SPECIFIC
    ----------
    O(n²) constraints, one LP call. ~15 ms for n=15 rooms.

    Examples                                                         ✱
    --------
    >>> plan = Plan.from_json("proposed.json")
    >>> q = legalize(plan, ctx)
    >>> q.certificate.geometry.valid
    True
    """
```

### The two sections specific to this project

**`Guarantees`** — mandatory on every function that returns a `Plan` or a `Certificate`.
It says **of what kind** each guarantee is. It is the thesis of the project written
into the documentation, just as into the types.

**`Complexity`** — mandatory on `geom`, `lmo`, `solve`. The project sells speed;
it must be documented, not assumed.

---

## 4. Writing rules

- [ ] A public function without a docstring = **CI failure**
- [ ] The summary fits on **one line**, in the imperative or present indicative
- [ ] Every `raise` documented in `Raises`
- [ ] Every `seed` parameter documented with its exact scope
- [ ] Every example is an **executable doctest**, not pseudo-code
- [ ] Private functions (`_name`): one line is enough
- [ ] **Never** a guarantee asserted without saying of what kind it is

---

## 5. Gallery — the template of an example

Each file of `docs/gallery/` is **self-contained** and fits on one screen.

````markdown
# Repair a generated plan

**Problem.** The model produced a plan where two partitions overlap by 3 cm
and where the bathroom is 4.6 m² instead of the regulatory 5 m².

**Solution.**

```python
import archlux as ax

plan = ax.Plan.from_json("generator_output.json")
ctx  = ax.Context(structure=..., orientation=ax.Orientation(deg=12), ...)

q = ax.legalize(plan, ctx)
print(q.certificate.report())
```

**Result.**

```
GEOMETRY                                        [EXACT]
  Overlap                none          verified
  Minimum areas          6/6           verified
  Maximum displacement   0.21 m
```

**What to remember.** The proposed layout is kept; only the
dimensions are adjusted. Maximum displacement: 21 cm.

**See also:** [Read a certificate](04-read-a-certificate.md)
````

**Imposed structure:** Problem → Solution → Result → What to remember → See also.
An example that does not first state a concrete problem is useless.

---

## 6. Automatic checking

```yaml
# .github/workflows/ci.yml — excerpt
- run: uv run pytest --doctest-modules src/archlux    # the examples run
- run: uv run ruff check --select D src/              # pydocstyle
- run: uv run interrogate -f 95 src/archlux           # docstring coverage
- run: uv run mkdocs build --strict                   # dead links = failure
```

- [ ] Doctests run in CI — a wrong example breaks the build
- [ ] Docstring coverage ≥ 95 % on `src/`
- [ ] `mkdocs build --strict`: every dead link fails
- [ ] Check that the gallery runs on a real plan, not a fictitious one

---

## 7. What is documented at each milestone

| Milestone | Documentation to produce |
|---|---|
| 1 | `README.md`, `installation.md`, JSON schema |
| **2** | **Gallery 01 and 03, `concepts/polytope.md`, `formulas/`, docstrings of `geom`/`lmo`/`certify`** |
| 3 | Gallery 02, `concepts/shared-oracle.md`, performance legalization tutorial |
| 4 | Surrogate tutorial, doc of the `Surrogate` protocol, **doc of `validate_gradient`** |
| 5 | Gallery 04 and 05, `concepts/two-guarantees.md`, `concepts/conformal-prediction.md` |
| 6 | `limitations.md`, contribution guide, 1.0 release notes |

**Rule: the documentation of a milestone is written during the milestone, not after.**
A milestone whose docs are missing is not finished.

---

## 8. CHANGELOG

[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format, semantic versioning.

```markdown
## [0.2.0] — 2026-11-14

### Added
- `light.AnalyticSurrogate`: closed-form daylight model, without learning.
- `solve.frank_wolfe` with away steps.

### Changed
- `lmo.solver.solve` accepts `start=` for warm start (×3 on the time).

### Fixed
- Area cuts could accumulate without bound (#42).
```

**Project-specific rule:** any change of behaviour of the oracle or of the
certificate is a **major version**. A certificate produced in `1.2.0` must stay
reproducible in `1.2.x`.

---

## 9. Anti-patterns

| Anti-pattern | Why |
|---|---|
| Writing the API reference first | Least useful order for adoption |
| Pseudo-code examples | They rot without anyone noticing |
| Guarantee asserted without its kind | Confuses proof and prediction — the central mistake of the project |
| Documentation postponed "to the end" | It is then written in a rush and serves nobody |
| No `limitations.md` page | A regulatory tool that does not say what it does not check is dangerous |
| Doctests not run in CI | They become wrong in three weeks |
| Examples on fictitious plans | They prove nothing, and hide the hard real cases |
