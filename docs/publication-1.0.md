# Publication 1.0.0 — checklist

Ce document prépare la publication logicielle. **Il ne remplace pas** les
conditions de recevabilité des revues (historique public, usage tiers).

## Prêt dans le dépôt

| Livrable | État |
|---|---|
| Version `1.0.0` (`_version.py`, source unique) | **non** : `0.10.0.dev0`, 1.0.0 reportée (PLAN.md phase 5) |
| API gelée + `test_api_publique_stable` | test présent ; gel reporté (renommage anglais, ADR 0001) |
| `CHANGELOG.md` section `1.0.0` | section retirée (jamais publiée) |
| `CITATION.cff` | oui (URL / DOI à finaliser) |
| Licence Apache-2.0 (fichier `LICENSE`) | oui (ajouté en phase 0) |
| Docs MkDocs (`mkdocs build --strict`) | oui |
| `CONTRIBUTING.md` | oui |
| Tests CI (dépendances, torch hors noyau) | oui |

## À faire hors code (mainteneurs)

1. Remplacer `ORG/archlux` dans `CITATION.cff`, `README`, `docs/contribution.md`
   par l'URL publique réelle.
2. Étiqueter `v1.0.0` et archiver (Zenodo / Software Heritage) → DOI dans
   `CITATION.cff`.
3. Publier la distribution sur l'index de paquets (`twine` / Trusted Publishing).
4. Joindre au dépôt public : poids du substitut, **jeu de calibration**,
   découpages `splits/`, résultats bruts du banc.
5. Attendre **≥ 6 mois** d'historique public étalé et **au moins un usage tiers**
   documenté avant une soumission de revue de logiciel
   (`MILESTONE-6.md` §7).

## Publication **scientifique** — ce qui manque encore

Cette page couvre la publication *logicielle*. Un article à comité de lecture
demande autre chose, et le dépôt n'y est pas.

| Exigence | État | Où |
|---|---|---|
| Méthode formulée, sourcée, dérivée | ✅ | `docs/formules/` (17 références localisées) |
| Implémentation vérifiable, typée, testée | ✅ | `mypy --strict` propre, couverture 89 % |
| Budgets de performance tenus | ✅ | `benchmarks/`, `ARCHITECTURE.md` §9 |
| **Étiquettes d'éclairement mesurées** | ❌ | forme fermée uniquement — [vérité terrain](donnees/verite-terrain.md) |
| **Corpus réel chargé** | ❌ | chargeur WKT à écrire (`data/chargeurs.py`) |
| **Baseline : 3 modèles génératifs publics** | ❌ | `MILESTONE-2.md` §8 ; jamais construite : `j2_brut.csv` contenait 2 plans faits à la main (retiré) ; revue [`j2`](revues/j2.md) |
| **Couverture conforme mesurée sur corpus réel** | ❌ | `n = 18` en calibration synthétique |
| Étude d'ablation (jetons, imputation des baies, actif vs aléatoire) | ⚠️ | scripts présents, résultats à l'échelle jouet |
| Comparaison à l'état de l'art | ❌ | aucune |

**Lecture honnête :** les jalons 1–6 démontrent qu'une *architecture* tient — deux
garanties séparées par construction, un solveur pour deux objectifs, un certificat
qui refuse de conclure quand l'échangeabilité tombe. C'est un résultat d'ingénierie
logicielle et de conception, défendable comme tel (article outil / JOSS-like, ou
section « méthode » d'un article plus large).

Ce n'est pas encore un résultat expérimental : aucune grandeur physique n'a été
mesurée, aucun générateur public n'a été corrigé, aucune baseline n'a été battue.

## Contrat d'API 1.x

Toute suppression ou renommage d'un symbole de `archlux.__all__` est une
**version 2.0**. Les ajouts non cassants restent en `1.x`.

Changement de comportement de `lmo` ou `certify` → version **majeure**
(reproductibilité des certificats).

## Citer

```bibtex
@software{archlux100,
  title   = {archlux: geometric legalization of generated floor plans
             with conformally bounded daylight surrogates},
  version = {1.0.0},
  year    = {2026},
  url     = {https://github.com/ORG/archlux},
  license = {Apache-2.0}
}
```

Préférer le DOI Zenodo une fois l'archive créée.
