# Contributing

The contribution guide (governance, review, versions, dependency rules)
is at the root of the repository: [`CONTRIBUTING.md`](https://github.com/ORG/archlux/blob/main/CONTRIBUTING.md).

Non-negotiable summary:

1. Read [`ARCHITECTURE.md`](specification/ARCHITECTURE.md) before any PR.
2. Exact geometry; probabilistic light — do not confuse the two.
3. `geom` / `lmo` / `solve` / `certify` **never** import `torch`.
4. A public function without a docstring is not finished.

**See also:** [Limitations](limitations.md), [Documentation](specification/DOCUMENTATION.md).
