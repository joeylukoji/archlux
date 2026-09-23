# ADR 0001 — English-first code base

- **Status:** accepted (2026-09-23)
- **Context:** PLAN.md, cross-cutting track E; AUDIT.md §4 (minor) and §11.

## Context

The library, its documentation and its specifications are written in French, while a
few public names are English (`legalize`, `Daylight`, `Loop`). The project targets
international users, an open-source release and a scientific article. Reviewers read
the code; JOSS requires English; PyPI users search in English. A mixed-language API is
the worst of both options.

## Decision

1. Code, public API, docstrings, error messages, tests, README, specifications, the
   documentation site and the article are written in **English**.
2. Domain terms are translated once, in the [glossary](../glossary.md).
3. The migration is **incremental**: one module or document per batch (at most about
   500 changed lines), each batch ending with a green test suite. A file is migrated
   when it is worked on anyway (PLAN.md phases 1–7).
4. **Renaming and refactoring never share a commit.** A rename commit is mechanical and
   must leave the reference cases byte-for-byte identical.
5. **All new code is written in English from now on**, even inside a module that is
   still French.
6. Public French names remain as aliases emitting `DeprecationWarning` until 1.0.0, then
   are removed.
7. The JSON format moves to schema v2 (English keys); the reader accepts v1 and v2, the
   writer emits v2, so existing certificates stay readable.

## Consequences

- About 15–20 % extra effort on PLAN.md phases 3, 4 and 7, none elsewhere.
- A CI check rejects non-English prose in files already migrated.
- A French translation of the README may exist (`README.fr.md`) but is not normative.
