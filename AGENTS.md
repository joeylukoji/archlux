# Dispatch des agents et skills

Fichier canonique pour **Cursor** et **Claude Code**.
À chaque nouvelle tâche : classer le travail, charger **uniquement** les skills concernés, lire leur `SKILL.md`, puis exécuter.

Contrainte projet : lire `docs/specification/ARCHITECTURE.md` avant toute modification. La géométrie est exacte ; la lumière est probabiliste. Ne jamais les confondre.

## Comment dispatcher

1. Identifier le type de tâche dans la table ci-dessous (plusieurs lignes peuvent matcher).
2. Charger les skills listés (lire `SKILL.md` ; suivre les fichiers liés).
3. **Claude Code** : déléguer aux sous-agents `.claude/agents/` du même nom (`skills:` déjà préchargés).
4. **Cursor** : invoquer les skills projet (`.cursor/skills/` et `.agents/skills/`).
5. Ne pas charger un skill hors table « juste au cas où ».
6. Après du code Python non trivial : enchaîner `review-and-refactor`.

## Table de routage

| Si la tâche… | Appeler | Ne pas appeler |
|---|---|---|
| Écrit, corrige, annote ou debug du **Python** | `python-expert` | `agent-browser` |
| Concevoir / découper un module, SRP, composition, couplage, God class | `python-design-patterns` puis `python-expert` | `architecture-blueprint-generator` (sauf doc d'ensemble) |
| Feature ou bug **test-first**, red-green, tests d'intégration | `tdd` + `python-expert` | refactor plan tant que le comportement n'est pas piné |
| **Planifier** un refactor (RFC, commits minuscules, issue) | `request-refactor-plan` | coder avant la fin du plan |
| **Revoir / nettoyer** du code existant selon les standards du repo | `review-and-refactor` | `tdd` sauf si les tests cassent |
| Documenter l'architecture (blueprint, diagrammes, ADR) | `architecture-blueprint-generator` | modifier le code dans la même passe |
| Naviguer un site, formulaire, screenshot, scrape, QA UI | `agent-browser` | les skills Python |

## Combos fréquents

| Demande utilisateur | Séquence |
|---|---|
| « implémente X » | `tdd` → `python-expert` → `review-and-refactor` |
| « refactor Y » | `request-refactor-plan` → (après accord) `tdd` → `python-expert` → `review-and-refactor` |
| « nouveau module / couche » | `python-design-patterns` → `python-expert` → `tdd` |
| « documente l'archi » | `architecture-blueprint-generator` (sortie `Project_Architecture_Blueprint.md`, sans contredire `docs/specification/ARCHITECTURE.md`) |
| « teste l'UI / ouvre le navigateur » | `agent-browser` |
| « review cette PR / ce diff » | `review-and-refactor` + `python-design-patterns` si le diff est structurel |

## Rôle de chaque agent

### `python-expert`

Écrire et relire du Python 3.11+ idiomatique. Priorité : **correctness → types → perf → style**. Pas d'archi multi-modules (ça c'est `python-design-patterns`).

### `python-design-patterns`

Décider comment **structurer** : KISS, SRP, composition, règle de trois, injection. Lire `references/details.md` si le navigateur du skill ne suffit pas.

### `tdd`

Boucle rouge → vert, une tranche verticale, seams publics seulement. Confirmer les seams avec l'utilisateur avant le premier test. Le refactor n'est **pas** dans la boucle (stage `review-and-refactor`).

### `request-refactor-plan`

Interview + exploration + plan de micro-commits + issue GitHub. **Ne pas implémenter** pendant ce skill. Restauré depuis l'archive mattpocock (retiré du repo amont ; successeurs amont : `to-spec` / `improve-codebase-architecture`).

### `review-and-refactor`

Revue senior après un diff. Pour ce repo, les instructions contraignantes sont `docs/specification/ARCHITECTURE.md` (et ce fichier), pas seulement `.github/instructions/`. Garder les fichiers existants ; ne pas éclater le code sans besoin. Relancer les tests s'il y en a.

### `architecture-blueprint-generator`

Analyser le repo et produire un blueprint extensible. Ne pas inventer une archi qui viole les 4 couches (`geom`, `lmo`, `solve`/`light`, `certify`).

### `agent-browser`

Automatisation navigateur (CLI `agent-browser`). Charger `agent-browser skills get core` avant la première commande. Préférer ce skill à tout autre outil browser.

## Emplacements

| Outil | Skills | Agents |
|---|---|---|
| Claude Code | `.claude/skills/` | `.claude/agents/` |
| Cursor | `.cursor/skills/` et `.agents/skills/` | règle `.cursor/rules/agent-dispatch.mdc` |
