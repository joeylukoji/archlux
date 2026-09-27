# Agent and skill dispatch

Canonical file for **Cursor** and **Claude Code**.
For each new task: classify the work, load **only** the relevant skills, read their `SKILL.md`, then execute.

Project constraint: read `docs/specification/ARCHITECTURE.md` before any change. Geometry is exact; light is probabilistic. Never confuse them.

## How to dispatch

1. Identify the task type in the table below (several rows may match).
2. Load the listed skills (read `SKILL.md`; follow the linked files).
3. **Claude Code**: delegate to the `.claude/agents/` subagents of the same name (`skills:` already preloaded).
4. **Cursor**: invoke the project skills (`.cursor/skills/` and `.agents/skills/`).
5. Do not load a skill outside the table "just in case".
6. After non-trivial Python code: chain `review-and-refactor`.

## Routing table

| If the task… | Call | Do not call |
|---|---|---|
| Writes, fixes, annotates or debugs **Python** | `python-expert` | `agent-browser` |
| Design / split a module, SRP, composition, coupling, God class | `python-design-patterns` then `python-expert` | `architecture-blueprint-generator` (except for overall docs) |
| **Test-first** feature or bug, red-green, integration tests | `tdd` + `python-expert` | refactor plan as long as the behaviour is not pinned |
| **Plan** a refactor (RFC, tiny commits, issue) | `request-refactor-plan` | coding before the plan is finished |
| **Review / clean up** existing code against the repo standards | `review-and-refactor` | `tdd` unless the tests break |
| Document the architecture (blueprint, diagrams, ADR) | `architecture-blueprint-generator` | changing the code in the same pass |
| Browse a site, form, screenshot, scrape, UI QA | `agent-browser` | the Python skills |
| Security review, untrusted input, auth, secrets, dependency/supply-chain audit | `agent-skills:security-auditor` (skill `agent-skills:security-and-hardening`) | — |
| Plan or execute a **deprecation/rename wave** (PLAN.md 3.9 style: old name kept as alias, then removed) | `agent-skills:deprecation-and-migration` | rewriting call sites without an alias period unless already agreed |
| Split a messy working tree into atomic commits, cut a release, pick a semver bump, write a changelog entry | `agent-skills:git-workflow-and-versioning` | — |

## Frequent combos

| User request | Sequence |
|---|---|
| "implement X" | `tdd` → `python-expert` → `review-and-refactor` |
| "refactor Y" | `request-refactor-plan` → (after agreement) `tdd` → `python-expert` → `review-and-refactor` |
| "new module / layer" | `python-design-patterns` → `python-expert` → `tdd` |
| "document the architecture" | `architecture-blueprint-generator` (output `Project_Architecture_Blueprint.md`, without contradicting `docs/specification/ARCHITECTURE.md`) |
| "test the UI / open the browser" | `agent-browser` |
| "review this PR / this diff" | `review-and-refactor` + `python-design-patterns` if the diff is structural |

## Role of each agent

### `python-expert`

Write and review idiomatic Python 3.11+. Priority: **correctness → types → perf → style**. No multi-module architecture (that is `python-design-patterns`).

### `python-design-patterns`

Decide how to **structure**: KISS, SRP, composition, rule of three, injection. Read `references/details.md` if the skill's navigator is not enough.

### `tdd`

Red → green loop, one vertical slice, public seams only. Confirm the seams with the user before the first test. Refactoring is **not** in the loop (`review-and-refactor` stage).

### `request-refactor-plan`

Interview + exploration + micro-commit plan + GitHub issue. **Do not implement** during this skill. Restored from the mattpocock archive (removed from the upstream repo; upstream successors: `to-spec` / `improve-codebase-architecture`).

### `review-and-refactor`

Senior review after a diff. For this repo, the binding instructions are `docs/specification/ARCHITECTURE.md` (and this file), not only `.github/instructions/`. Keep the existing files; do not split the code without need. Rerun the tests if there are any.

### `architecture-blueprint-generator`

Analyse the repo and produce an extensible blueprint. Do not invent an architecture that violates the 4 layers (`geom`, `lmo`, `solve`/`light`, `certify`).

### `agent-browser`

Browser automation (`agent-browser` CLI). Load `agent-browser skills get core` before the first command. Prefer this skill over any other browser tool.

### `agent-skills:security-auditor` / `agent-skills:security-and-hardening`

Vulnerability and hardening pass (OWASP-style): untrusted input, auth, storage, third-party integrations, dependency audits. Complements `review-and-refactor`, does not replace it.

### `agent-skills:deprecation-and-migration`

How to age out an old name, API or schema version without breaking callers (expand/contract, alias windows, sunset criteria). Use it to plan a wave before running `scripts/rename_identifiers.py`, not instead of it.

### `agent-skills:git-workflow-and-versioning`

Atomic commits, branch/PR hygiene, semver bumps, changelog writing.

**Overlaps, kept out of automatic dispatch to avoid duplicate work:** `agent-skills:code-reviewer` and `agent-skills:test-engineer` cover the same ground as `review-and-refactor` and `tdd` on this repo. Invoke them by name only if asked explicitly (e.g. a second opinion, or a dedicated coverage-gap audit distinct from red-green).

## Locations

| Tool | Skills | Agents |
|---|---|---|
| Claude Code | `.claude/skills/` | `.claude/agents/` |
| Cursor | `.cursor/skills/` and `.agents/skills/` | rule `.cursor/rules/agent-dispatch.mdc` |
| `agent-skills:*` rows | plugin installed by the user, not in this repository | same |
