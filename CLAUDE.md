# Claude Code — archlux

Before any task: read `AGENTS.md` and dispatch to the relevant subagents / skills.

Read `docs/specification/ARCHITECTURE.md` before changing the code. Exact geometry; probabilistic light.

## Subagents (delegate automatically)

The descriptions in `.claude/agents/` are the routing signal. Delegate **proactively** as soon as a row of `AGENTS.md` matches.

| Agent | Preloaded skill |
|---|---|
| `python-expert` | `python-expert` |
| `python-design-patterns` | `python-design-patterns` |
| `tdd` | `tdd` |
| `request-refactor-plan` | `request-refactor-plan` |
| `review-and-refactor` | `review-and-refactor` |
| `architecture-blueprint-generator` | `architecture-blueprint-generator` |
| `agent-browser` | `agent-browser` |

After non-trivial Python code, chain `review-and-refactor`.

## From the `agent-skills` plugin (routed automatically when installed)

- `agent-skills:security-auditor`, `agent-skills:deprecation-and-migration`, `agent-skills:git-workflow-and-versioning` — routed by `AGENTS.md` like the agents above. The plugin is **not vendored** in this repository: it must be installed in the user's Claude Code. Without it, skip these rows; nothing else depends on them.

## Available on demand (not auto-dispatched)

- `ponytail` (`/ponytail`, `/ponytail-review`, `/ponytail-audit`) — pushes toward the most minimal, densest code. **Not** dispatched automatically here: it conflicts with this repo's own conventions (numpy docstrings, `ARCHITECTURE.md`'s explicitness, `review-and-refactor`). Invoke it by name only if explicitly asked for a concision pass.
