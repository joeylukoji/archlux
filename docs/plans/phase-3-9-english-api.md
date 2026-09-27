# Refactor plan: an English public API (PLAN.md 3.9, tracks E4 to E21)

Status: **waves 0 to 6 implemented** (2026-09-27). Written with the `request-refactor-plan`
skill, after measuring the codebase. The open question below (parameter aliases) is still
unresolved; PLAN.md phase 4 (the design-pattern restructuring) starts after it.

## Problem Statement

The public API mixes two languages. `legalize`, `Daylight` and `Loop` sit next to `Piece`,
`Contexte`, `Infaisable` and `verifier_exactement`. A reader who does not read French cannot
tell what `deplacement_max`, `jours` or `duaux` mean, and reviewers of the article, JOSS and
PyPI users all read the code (ADR 0001).

PLAN.md sized this at "about 25 symbols". Measured on 2026-09-25 it is much larger:

- roughly **200 public names** across 17 packages are French (classes, functions, constants,
  keyword parameters), and **10 model types** carry about 45 French field names;
- the main types are used everywhere: `Piece` about 370 times, `Contexte` about 240,
  `Referentiel` about 130, `InvariantViole` about 350, of which 247 in the library itself;
- about 35 module files and 5 directory names (`tests/unit`, `tests/properties`,
  `experiments`, `results`, `tests/references`) are French;
- the room types are French *data* (`sejour`, `chambre`, `sdb`...) stored in JSON files,
  regulations and surrogate encoders.

A single "big bang" rename would be an unreviewable diff that also mixes a rename with
behaviour, which ADR 0001 forbids.

## Solution

Rename in **waves**, each a series of small mechanical commits that leaves the suite green,
in the order that keeps every intermediate state usable:

1. tooling, so that a rename is mechanical, proven mechanical, and cheap to review;
2. the exceptions, then the model classes, then the fields of the model;
3. the JSON format (schema v2, English keys and room-type values);
4. every module in turn (files, functions, parameters, docstrings);
5. the directory names.

Decisions taken with the maintainer (2026-09-25):

- French **class, function and module names stay importable as deprecated aliases** that
  emit a `DeprecationWarning` until 1.0.0, then are deleted.
- French **field names are renamed with no alias**: a clean break before 1.0. The JSON v1
  format stays readable.
- French **room-type values** (`sejour`...) change with the JSON v2 wave, not with the
  code renames.

## Commits

Every commit leaves `pytest`, `ruff check`, `ruff format --check` and `mypy src/` green.
A rename commit contains **only** a rename; a refactor never shares a commit with one.

### Wave 0: tooling and safety nets (no rename yet)

1. Glossary: add the terms the later waves need and that are missing (exception names, the
   fields of each model type, function and parameter names). A term must be in the glossary
   before a module using it is renamed.
2. One helper builds a module-level lazy alias table (old name to new name, one
   `DeprecationWarning` per access, message "X is deprecated, use Y; removed in 1.0.0").
3. Replace the four hand-written copies of that logic (old `preuve` module, `light` package,
   `SimulateurExact` in the oracle module, trace aliases) by the helper. The existing alias
   tests pass unchanged: this proves the helper.
4. Add the rename tool. It works on Python files and on the Python code blocks of the
   documentation; it renames identifiers on word boundaries, understands keyword arguments
   of calls and attribute access, has a dry-run mode, and **refuses to guess**: an ambiguous
   match (a field name shared by several classes) is reported, not changed. It never touches
   the alias tables nor the JSON keys.
5. Add a proof mode to the tool: apply the inverse mapping to the renamed tree and compare
   the syntax trees with the original. Equal trees prove that a commit is a pure rename.
6. Add the neutrality check: a fixed corpus of JSON v1 plans (taken from the guarantee
   benchmark scenarios) is legalized and written back to JSON, and the hash of the output is
   compared with a committed baseline. Waves 1 to 3 must not change one byte of it.
7. Add the identifier guard: for the modules listed as migrated, no class, function,
   parameter or attribute name may be a French term of the glossary. The list starts empty.

### Wave 1: exceptions

8. Add the glossary entries: eight exception classes and their attributes.
9. Rename the exception classes and their attributes across library, tests, benchmarks,
   experiments and documentation.
10. Add their deprecated aliases and one parametrized test over the whole alias table.
11. Rename the module holding them and keep the old module path as a deprecated re-export.
12. CHANGELOG entry.

### Wave 2: model classes (one commit per class, alias and test included)

13. Room, Wall, Opening, Context, Regulation, Certificate, GeometricProof,
    PerformanceBound, Manifest: nine commits. The benchmark package exports a `Manifest`
    alias of the model's manifest class: the rename removes that duplicate instead of
    creating a second one.
14. Public package root: export the new names, keep the old ones as aliases, not advertised
    in `__all__`.

### Wave 3: model fields (clean break, one commit per type)

15. Wall, Opening, Structure, Regulation (and its `a_min` method), GeometricProof,
    PerformanceBound, Certificate, Manifest (and its model-trace companion), Context. Each field name is unique enough to rename
    project-wide after the tool has listed the collisions.
16. Plan: `pieces`, `murs`, `ouvertures`, `contour`, `certificat`. These names are shared
    with other classes (relative order, constraint graph, polytope), so this commit is
    guided by the type checker: rename the field, let mypy list every broken access, fix
    exactly those, then run the suite.
17. In every commit of this wave the JSON writer and reader keep the **v1 keys** through an
    explicit mapping, so the neutrality check stays byte-identical.

### Wave 4: JSON schema v2 and room-type values

18. Publish the v2 schema file (English keys) and its documentation page.
19. The writer emits v2; the reader accepts v1 and v2. Round-trip tests v1 to v2 and v2 to
    v2. Old certificates stay readable.
20. Room-type values move to English everywhere (library tables, regulations, encoders,
    tests, documentation). The v1 reader maps the old values. Encoders index by position, so
    their outputs are unchanged.
21. The neutrality check switches from JSON text to the geometry and the proof flags of each
    legalized plan, since the text legitimately changed.

### Wave 5: modules, one batch each

Order of PLAN.md tracks E6 to E19: model, geometry, LMO, solver, daylight, orientation,
uncertainty, certification, feasibility, public API, active learning, export, data, bench.
For each module:

22. Rename files, functions, keyword parameters, docstrings and comments to the glossary.
23. Add the deprecated module path and function aliases, and their tests.
24. Add the module to the identifier guard and to the list of migrated files of the
    language test.

### Wave 6: directory names

25. `tests/unit`, `tests/properties`, `tests/references`, then `experiments` and
    `results` (these two touch the Makefile, the results script, the fingerprint file,
    the CI workflow and the documentation), one commit each.

## Decision Document

- **Aliases.** Classes, functions and modules keep their French names as deprecated aliases
  until 1.0.0; one shared helper implements them. Aliases are not listed in `__all__` and
  are removed in the 1.0.0 commit.
- **Fields and parameters.** Fields are renamed with no alias. Keyword parameters of public
  functions (`pavage`, `budget_reparation`, `depart`, `baies`...) follow the same policy
  *by default*: **this was not asked explicitly**, see "Open question".
- **JSON.** Schema v2 has English keys and English room-type values. Reader: v1 and v2.
  Writer: v2 only. The v1 keys remain the writer's output until wave 4.
- **Neutrality.** A wave that only renames must not change the output of the library on the
  fixed corpus, byte for byte, until wave 4 changes the text format.
- **Collisions.** Renames that would merge two distinct classes of the same target name are
  resolved before the rename, not during it.
- **Not renamed.** `Plan`, `Structure`, `Orientation`, `legalize` and the daylight
  indicator names (`sDA`, `ASE`, `UDI`, `vue`) already read in English or are standard
  acronyms.
- **Version.** Pre-1.0: the API break of the field renames ships in a minor release. The
  maintainer chooses the number.

## Testing Decisions

- A good test here checks external behaviour: the alias returns the same object and warns
  once; the old JSON still loads; the output bytes did not move. It does not check that a
  private helper was called.
- The rename tool is tested on small fixture trees: a keyword argument, an attribute of
  another class with the same name, a string, a docstring, a documentation code block.
- All aliases are covered by one parametrized test over the alias table, instead of one file
  per alias as the existing precedent does.
- Prior art: the alias tests for the split-flux oracle and the trace, the language test for
  migrated files, the dependency test for layers, the JSON schema tests, and the guarantee
  benchmark that measures 0 false certificates.
- Gate for every commit: full suite, `ruff`, `mypy src/`, the documentation examples test,
  and from wave 0.6 the neutrality check. Gate for every wave: the guarantee benchmark
  counts equal to the recorded baseline, and `make check-results`.

## Out of Scope

- Removing the aliases: that is the 1.0.0 release.
- Translating the documentation site, `AUDIT.md` and `PLAN.md` (tracks E22 and E23).
- Any behaviour change and any structural refactor of a module (PLAN.md phase 4). A module
  is renamed first and refactored later, in separate commits.
- New features, including CLI and DXF input (phase 5).

## Further Notes

- **Size.** About 60 commits. Waves 1 to 3 are large in diff-stat but mechanical; the proof
  mode of the rename tool makes them reviewable by their mapping, not line by line.
- **Risks.** A field name shared by unrelated classes (mitigated by the type-checker-guided
  commit and by the tool refusing ambiguous matches); string keywords such as the ones given
  to `dataclasses.replace`; documentation code blocks, which the documentation test executes
  and will catch; Windows line endings, which a past batch already tripped on.
- **Open question for the maintainer.** Should keyword parameters of the public functions
  (`legalize(pavage=..., budget_reparation=...)`, `Frank-Wolfe depart=`) get a deprecation
  shim like the classes, or break cleanly like the fields? A shim needs a wrapper on each
  function and roughly doubles the tests of wave 5.
