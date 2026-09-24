# archlux

> **Corriger un plan généré vers la validité géométrique en préservant sa lumière
> naturelle. La géométrie est prouvée ; la lumière est bornée.**

Version française abrégée et **non normative** ([ADR 0001](docs/adr/0001-english-first.md)).
La page de référence est le [README anglais](README.md), dont les exemples de code sont
exécutés par la suite de tests.

## Dans quel régime l'outil fonctionne

archlux répare des plans **presque** justes. Sur 4 796 corruptions de 300 appartements
réels (corpus MSD : jours, chevauchements, pièces sous-dimensionnées ou décalées), il rend
un plan certifié valide dans **93,9 %** des cas (IC 95 % [93,2 ; 94,5], mode pavage avec
repli ; `resultats/j7_reparation.md`). Sur des sorties brutes de modèle génératif
(HouseDiffusion, 740 plans, aucun valide au départ), il ne rend un plan certifié
**intact** que dans **environ 20 %** des cas (17,8 % à 23,0 % selon le jeu ;
`resultats/j8_generation.md`) : quatre plans sur cinq sont trop loin d'un pavage exact
pour être réparés sans perdre une pièce. Ces deux chiffres précèdent les contraintes de
murs porteurs du lot 1.1 et seront remesurés (PLAN.md, J7 et J8).

## Les deux garanties

| | Géométrique | Lumière |
|---|---|---|
| **Nature** | Exacte, sur le modèle (rectangles axés) | Probabiliste |
| **Vérification** | `certify.proof.verify_exactly` : arithmétique rationnelle sur contour rectangulaire axé (seule tolérance : arêtes à moins de 1e-7 m identifiées), GEOS et tolérances déclarées sinon | Prédiction conforme sur un jeu de calibration |
| **Infaisabilité** | Certificat de Farkas vérifié exactement, **pour l'ordre relatif proposé** (« infeasible for this relative order ») | — |
| **Régime** | — | `"exchangeable"` : couverture ≥ 1 − α garantie. `"selected"` : plan choisi par l'optimiseur, couverture **non** garantie |

`legalize(..., objective=..., calibration=...)` rend toujours une borne en régime
`"selected"`, et le rapport l'écrit (« couverture NON garantie »). Sans `calibration`,
`certificat.performance` vaut `None`. La borne porte sur l'oracle contre lequel on a
calibré — dans le dépôt, `OracleSplitFlux`, une **forme fermée** split-flux gelée, ni une
simulation ni une vérité terrain — jamais sur un sDA LM-83 mesuré.

## Ce qui n'existe pas encore

- **Géométrie non-Manhattan** : non supportée (un mur porteur oblique lève
  `UnsupportedInput`). Les pièces en L passent par une fusion de rectangles.
- **Front de Pareto** sDA / ASE : aucun code.
- **Transformeur appris** : `SubstitutAppris` refuse les poids `.pt`.
- **Étiquettes d'éclairement physiques** : la CI utilise une forme fermée
  ([`docs/donnees/verite-terrain.md`](docs/donnees/verite-terrain.md)).

## Démarrer

```bash
pip install -e ".[dev]"
```

Puis suivre le [démarrage rapide du README anglais](README.md#quick-start). La
documentation détaillée ([`docs/`](docs/)) est encore en français ; les limites sont dans
[`docs/limites.md`](docs/limites.md), l'architecture dans
[`docs/specification/ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md).

> **Un plan produit par ce système est une proposition, jamais un document de projet.
> La responsabilité de conception et de signature demeure celle d'un professionnel
> habilité.**

Licence Apache 2.0 — voir [`LICENSE`](LICENSE).
