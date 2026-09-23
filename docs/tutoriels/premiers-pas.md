# Premiers pas

Installer le noyau (sans PyTorch) :

```bash
pip install archlux
```

## Un plan, un contexte, une correction

L'enveloppe et les pièces ci-dessous sont celles du corpus de tests publié
(`CONTEXTE_DEFAUT` : 12 m × 9 m) — pas une géométrie inventée pour la doc.

```python
import archlux as ax

contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    pieces=(
        ax.Piece(id="sejour", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Piece(id="chambre", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    murs=(),
    ouvertures=(),
    contour=contour,
)
ctx = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=0.0),
    contour=contour,
    referentiel=ax.Referentiel(aires_min=(), largeur_min=1.0),
)

q = ax.legalize(plan, ctx)
assert q.certificat is not None
assert q.certificat.geometrie.valide
assert q.certificat.performance is None  # légalisation classique : pas de borne
print(q.certificat.rapport())
```

`legalize` renvoie un plan **prouvé** valide (pavage, surfaces, porteurs).
La section `[PREDICTION]` du rapport reste `NON EVALUABLE` tant qu'aucune
calibration conforme n'a été attachée.

## Charger depuis un fichier

```python
plan = ax.Plan.from_json("sortie_generateur.json")
q = ax.legalize(plan, ctx)
q.to_json("plan_legalise.json")
```

Le schéma JSON est versionné ; voir [référence](../reference/schema-json.md).

## Suite

| Besoin | Page |
|---|---|
| Voir le même exemple commenté | [Corriger un plan](../galerie/01-corriger-un-plan.md) |
| Comprendre preuve ≠ prédiction | [Les deux garanties](../concepts/deux-garanties.md) |
| Maximiser la lumière sous validité | [Légalisation performantielle](legalisation-performantielle.md) |
| Ce que le système ne vérifie pas | [Limites](../limites.md) |
