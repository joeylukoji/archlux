# Contribuer à archlux

Merci. Avant toute contribution, lire
[`docs/specification/ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md)
et [`docs/specification/DOCUMENTATION.md`](docs/specification/DOCUMENTATION.md).

## Principes non négociables

1. **Géométrie exacte ; lumière probabiliste.** Ne jamais confondre les deux
   natures dans les types, messages d'erreur, certificats ou documentation.
2. **Règles de dépendance** (`ARCHITECTURE.md` §5) : vérifiées par
   `tests/test_dependances.py`. En particulier :
   - `geom`, `lmo`, `solve`, `certify` **n'importent jamais** `torch` ;
   - `lmo` n'importe pas `light` ;
   - `light` n'importe pas `geom` / `lmo` / `solve` ;
   - personne n'importe `bench` depuis le noyau ;
   - `active` n'importe que `light.protocole`, jamais une implémentation.
3. Une fonction **publique** sans docstring NumPy n'est pas terminée.
4. Une graine d'aléa a **toujours** un paramètre explicite, sans défaut.

## Comment travailler

1. Ouvrir une issue (ou commenter une issue existante) avant un changement
   structurel.
2. Une PR = une intention. Préférer plusieurs micro-commits à un monolithe.
3. Les tests d'abord pour un comportement nouveau (`tests/unites/`,
   `tests/proprietes/`). Les seams publics seulement.
4. Après du Python non trivial : relancer au minimum
   `pytest tests/test_dependances.py` et les tests du module touché ;
   `ruff check` + `mypy` sur les fichiers modifiés.
5. La documentation du comportement nouveau (galerie, formule ou concept)
   fait partie de la définition de « terminé ».

## Gouvernance

| Décision | Qui | Où |
|---|---|---|
| Changement de couche / dépendance | Mainteneurs | Issue + ADR dans le blueprint si durable |
| Rupture d'API publique (`archlux.__all__`) | Mainteneurs | Version **majeure** |
| Correctif / doc / test | Tout contributeur | PR revue |
| Version | Mainteneurs | `CHANGELOG.md` (Keep a Changelog) + semver |

**Revue.** Au moins une relecture pour les PR qui touchent `geom`, `lmo`,
`solve`, `certify`, `uq` ou `tests/test_dependances.py`. Une PR qui casse
`test_le_noyau_n_importe_pas_torch` est refusée sans discussion.

**Versions.** Semver. Tout changement de comportement de l'oracle (`lmo`) ou
du certificat (`certify`) est une **version majeure** : un certificat produit
en `1.2.0` doit rester reproductible en `1.2.x`.

## Structure utile

| Chemin | Rôle |
|---|---|
| `src/archlux/` | Code |
| `tests/` | Unités, propriétés, budgets |
| `docs/` | Site MkDocs (`mkdocs build --strict`) |
| `docs/specification/ARCHITECTURE.md` | Règles contraignantes |
| `experiences/` | Scripts de reproduction des tableaux |

## Licence

En contribuant, vous acceptez que vos contributions soient publiées sous
**Apache-2.0** (voir [`LICENSE`](LICENSE)).
