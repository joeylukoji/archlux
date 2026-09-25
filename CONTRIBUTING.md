# Contributing to archlux

Thank you. Before any contribution, read
[`docs/specification/ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md)
and [`docs/specification/DOCUMENTATION.md`](docs/specification/DOCUMENTATION.md).

## Non-negotiable principles

1. **Exact geometry; probabilistic light.** Never confuse the two
   kinds in types, error messages, certificates or documentation.
2. **Dependency rules** (`ARCHITECTURE.md` §5): checked by
   `tests/test_dependances.py`. In particular:
   - `geom`, `lmo`, `solve`, `certify` **never import** `torch`;
   - `lmo` does not import `light`;
   - `light` does not import `geom` / `lmo` / `solve`;
   - nobody imports `bench` from the core;
   - `active` imports only `light.protocole`, never an implementation.
3. A **public** function without a NumPy docstring is not finished.
4. A random seed **always** has an explicit parameter, with no default.
5. **English-first.** All new code, docstrings, messages and documentation are
   written in English, using the terms of `docs/glossary.md`. Existing French code
   is migrated batch by batch; a rename and a refactor never share a commit
   (`docs/adr/0001-english-first.md`).

## How to work

1. Open an issue (or comment on an existing issue) before a structural
   change.
2. One PR = one intent. Prefer several micro-commits to a monolith.
3. Tests first for new behaviour (`tests/unites/`,
   `tests/proprietes/`). Public seams only.
4. After non-trivial Python: rerun at least
   `pytest tests/test_dependances.py` and the tests of the touched module;
   `ruff check` + `mypy` on the modified files.
5. Documentation of new behaviour (gallery, formula or concept)
   is part of the definition of "done".

## Governance

| Decision | Who | Where |
|---|---|---|
| Layer / dependency change | Maintainers | Issue + ADR in the blueprint if lasting |
| Public API break (`archlux.__all__`) | Maintainers | **Major** version |
| Fix / doc / test | Any contributor | Reviewed PR |
| Release | Maintainers | `CHANGELOG.md` (Keep a Changelog) + semver |

**Review.** At least one review for PRs that touch `geom`, `lmo`,
`solve`, `certify`, `uq` or `tests/test_dependances.py`. A PR that breaks
`test_le_noyau_n_importe_pas_torch` is rejected without discussion.

**Versions.** Semver. Any change in the behaviour of the oracle (`lmo`) or
of the certificate (`certify`) is a **major version**: a certificate produced
with `1.2.0` must remain reproducible with `1.2.x`.

## Useful structure

| Path | Role |
|---|---|
| `src/archlux/` | Code |
| `tests/` | Units, properties, budgets |
| `docs/` | MkDocs site (`mkdocs build --strict`) |
| `docs/specification/ARCHITECTURE.md` | Binding rules |
| `experiences/` | Scripts reproducing the tables |

## AI-assisted development

The project is developed with coding agents (Claude Code, Cursor). Their routing rules
are versioned so that any contributor gets the same workflow: `AGENTS.md`, `CLAUDE.md`,
`.claude/agents/` and `.cursor/rules/`.

The skills those agents load are **third-party** (see `skills-lock.json` for sources and
hashes) and are **not** redistributed in this repository. Reinstall them with your agent
tooling from `skills-lock.json`. Local session state (`session_memory.json`) is ignored.

## License

By contributing, you agree that your contributions are published under
**Apache-2.0** (see [`LICENSE`](LICENSE)).
