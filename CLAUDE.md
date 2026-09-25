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
