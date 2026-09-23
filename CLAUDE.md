# Claude Code — archlux

Avant toute tâche : lire `AGENTS.md` et dispatcher vers les sous-agents / skills concernés.

Lire `docs/specification/ARCHITECTURE.md` avant de modifier le code. Géométrie exacte ; lumière probabiliste.

## Sous-agents (déléguer automatiquement)

Les descriptions dans `.claude/agents/` sont le signal de routage. Déléguer **proactively** dès qu'une ligne de `AGENTS.md` matche.

| Agent | Skill préchargé |
|---|---|
| `python-expert` | `python-expert` |
| `python-design-patterns` | `python-design-patterns` |
| `tdd` | `tdd` |
| `request-refactor-plan` | `request-refactor-plan` |
| `review-and-refactor` | `review-and-refactor` |
| `architecture-blueprint-generator` | `architecture-blueprint-generator` |
| `agent-browser` | `agent-browser` |

Après du code Python non trivial, enchaîner `review-and-refactor`.
