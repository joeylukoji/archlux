# Validation indépendante

Que le solveur déclare un plan admissible ne suffit pas. Avant que `legalize` ne
renvoie un plan, une **seconde vérification, indépendante**, le relit à partir de ses
seules coordonnées (ni statut du programme linéaire, ni polytope, ni trace de
Frank-Wolfe) et revérifie chaque règle explicite. Un plan n'est renvoyé que si toutes
les règles **dures** sont de nouveau satisfaites ; sinon `legalize` lève
`InvariantViolation`. Un bogue du solveur ne peut pas se certifier lui-même.

## Ce qui est vérifié

Chaque règle a un identifiant, un type, une tolérance et une méthode. Chaque résultat
est `satisfied`, `violated` ou `unknown`, avec la pire valeur mesurée et une raison. Une
vérification qui ne peut pas s'exécuter est `unknown`, **jamais** `satisfied`, et une
règle dure `unknown` fait refuser le plan comme une règle violée.

| Type | Règles |
|---|---|
| **Dures** (jamais violées par un plan renvoyé) | `rooms.finite`, `rooms.non_degenerate`, `ids.unique`, `rooms.no_overlap`, `outline.covered`, `outline.contains_rooms`, `rooms.min_area` (une pièce fusionnée prise comme un tout), `rooms.min_width`, `structure.not_crossed`, `structure.not_moved`, `walls.non_degenerate`, `openings.on_known_wall`, `openings.within_wall`, `openings.disjoint`, `openings.sill_below_head`, `displacement.budget` (si un budget est donné) |
| **Souples** (signalées, jamais bloquantes) | `rooms.connected` |

Les contraintes ajoutées pendant l'optimisation (une coupe, un contact figé) peuvent
être passées à `archlux.certify.validate_plan(..., extra=...)` et sont vérifiées selon
le même schéma.

## Exacte ou numérique : la nature de la preuve

Une validation n'est pas toujours une preuve. Le rapport dit laquelle :

| Nature | Signification | Bandeau du rapport |
|---|---|---|
| `exact` | chaque règle dure a été tranchée en **arithmétique rationnelle exacte** (les flottants stockés lus comme des fractions) face à une tolérance déclarée | `[EXACT]` |
| `numeric` | au moins une règle dure repose sur un calcul en **virgule flottante** (GEOS) avec tolérance — typiquement un contour non rectangulaire ou une pièce fusionnée | `[NUMERIC]` |
| `refused` | une règle dure est violée ou inconnue : aucun plan n'est renvoyé | — |

La tolérance fait partie de l'affirmation : « aucun chevauchement » signifie « aucun
chevauchement de plus de \(10^{-9}\ \text{m}^2\) », et le rapport affiche la tolérance à
côté de chaque mesure.

## Ce qu'elle n'établit jamais

Quel que soit le verdict, la validation porte sur le modèle géométrique explicite
ci-dessus et sur rien d'autre. Elle n'établit **pas** la conformité au code de la
construction, l'accessibilité, la sécurité incendie, la solidité structurelle, la
constructibilité ni la performance d'éclairement. Le résumé porte cette liste (`scope`)
pour qu'aucun lecteur n'ait à la deviner.

## La lire dans un certificat

```python
import archlux

plan = archlux.Plan(
    rooms=(
        archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=5.0, h=9.0),
        archlux.Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=9.0),
    ),
    outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
)
ctx = archlux.Context(
    structure=archlux.Structure(load_bearing_walls=()),
    orientation=archlux.Orientation(deg=180.0),
    regulation=archlux.Regulation(min_areas=(), min_width=1.0),
)
fixed = archlux.legalize(plan, ctx)
summary = fixed.certificate.validation
assert summary.valid and summary.evidence == "exact"
assert "rooms.no_overlap" in summary.checked
assert "fire safety" in summary.scope

# The full report, one measure per rule, recomputed on demand:
from archlux.certify import validate_plan

print(validate_plan(fixed, ctx).summary())
```

Le résumé est lié au plan qu'il a vérifié par une empreinte de sa géométrie
(`summary.plan_fingerprint`) ; `validate_plan(...).matches(plan)` confirme qu'un rapport
porte sur le plan final et non sur un état intermédiaire.

## Comment l'optimiseur s'est arrêté

Avec un objectif, le certificat enregistre aussi comment Frank-Wolfe s'est arrêté
(`certificate.optimization` : statut, itérations, écart). Tout statut renvoie un plan du
domaine admissible, donc la géométrie ci-dessus tient dans tous les cas ; mais seul
`converged` signifie que l'exécution a atteint sa tolérance de stationnarité. Tout autre
statut (`max_iter`, `stalled`, `line_search_failed`, `untrusted_gradient` quand un
substitut gardé a refusé son gradient…) est affiché comme « géométriquement valide, PAS
un plan optimisé ». Aucun statut ne signifie « optimum global » : aucun substitut livré
n'est concave.
