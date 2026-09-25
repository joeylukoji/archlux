"""Les règles de dépendance de `ARCHITECTURE.md` §5 sont exécutables, pas déclaratives.

Ce fichier est écrit **avant** toute implémentation, et non après. Une violation de
couche découverte au jalon 4 coûte un refactor ; découverte au premier commit, elle coûte
une minute. La CI l'exécute dans une étape dédiée et bloquante.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1] / "src" / "archlux"

# Ce que chaque paquet a le droit d'importer, à l'intérieur d'archlux.
# `solve` dépend de `light.protocole` SEULEMENT, jamais d'une implémentation.
AUTORISE: dict[str, frozenset[str]] = {
    "__init__": frozenset({"types", "erreurs", "api", "io"}),
    # `types` peut joindre `erreurs` : les deux sont des racines du graphe, `erreurs` ne
    # dépend de rien et n'importe surtout pas `types`. L'arête ne crée aucun cycle et
    # évite que chaque type doive lever `Exception` nue faute d'exception typée sous la
    # main (`ARCHITECTURE.md` §7).
    "types": frozenset({"erreurs"}),
    "erreurs": frozenset(),
    # Leaves importable by every layer; they import nothing (see LEAVES below).
    "_version": frozenset(),
    "tolerances": frozenset(),
    "seeds": frozenset(),
    "geom": frozenset({"types", "erreurs"}),
    "lmo": frozenset({"types", "erreurs", "geom"}),
    "solve": frozenset({"types", "erreurs", "geom", "lmo", "light.protocole"}),
    "light": frozenset({"types", "erreurs", "orient"}),
    "orient": frozenset({"types", "erreurs"}),
    "uq": frozenset({"types", "erreurs"}),
    # `data.chargeurs` convertit un corpus reel (WKT) en `Plan` : il redresse via
    # `orient.circulaire.direction_dominante` et decoupe via `geom.rectilineaire`.
    # Aretes ajoutees a `ARCHITECTURE.md` §5 : `geom` et `orient` sont purs et
    # n'importent pas `data`, donc aucun cycle. `data` ne touche ni `lmo`, ni
    # `solve`, ni `light` : il produit des entrees, il ne resout rien.
    "data": frozenset({"types", "erreurs", "uq", "orient", "geom"}),
    "certify": frozenset({"types", "erreurs", "geom", "uq"}),
    "io": frozenset({"types", "erreurs"}),
    # Apprentissage actif : orchestrateur feuille — protocole light + uq, pas torch.
    "active": frozenset({"types", "erreurs", "light.protocole", "uq"}),
    # Export BIM : feuille — types + erreurs ; ifcopenshell optionnel (hors archlux).
    "export": frozenset({"types", "erreurs"}),
    # Faisabilité : façade sur legalize / Farkas — exacte, sans lumière.
    "feasibility": frozenset({"types", "erreurs", "api"}),
    "bench": frozenset(
        {
            "types",
            "erreurs",
            "geom",
            "lmo",
            "solve",
            "light",
            "orient",
            "uq",
            "certify",
            "io",
            "data",
            "active",
            "export",
        }
    ),
    "api": frozenset(
        {"types", "erreurs", "geom", "lmo", "solve", "light.protocole", "certify", "io"}
    ),
}

LEAVES: dict[str, frozenset[str]] = {
    "_version": frozenset(),
    "tolerances": frozenset({"__future__", "typing"}),
    "seeds": frozenset({"__future__", "hashlib"}),
}
"""Modules importable by every layer, with the only imports they may make themselves."""

# torch n'est tolérable que dans light.appris, et en import paresseux.
TORCH_TOLERE = frozenset({"light.appris"})

# Dérogations nominatives, chacune adossée à une décision écrite (ADR-5 du blueprint).
# `Plan.from_json` et `Certificat.rapport()` sont l'API publique fixée par
# `DOCUMENTATION.md` §3 et §5. Les honorer demande à `types` de déléguer vers `io` et
# `certify` — par import **local**, à l'appel, donc sans cycle à l'import.
# La dérogation est nominative et non un assouplissement de la règle : tout autre import
# depuis `types` échoue toujours.
EXEMPTIONS: dict[str, frozenset[str]] = {
    "types": frozenset({"archlux.io.json_io", "archlux.certify.rapport"}),
}


def _modules() -> list[Path]:
    """Tous les modules, ``__init__.py`` **compris**.

    Les exclure laisserait un trou béant : un paquet peut violer une couche depuis son
    ``__init__``, et c'est même l'endroit le plus probable.
    """
    return sorted(RACINE.rglob("*.py"))


def _paquet(fichier: Path) -> str:
    rel = fichier.relative_to(RACINE)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def _chemin_module(fichier: Path) -> str:
    rel = fichier.relative_to(RACINE).with_suffix("")
    return ".".join(rel.parts)


def _imports(fichier: Path) -> set[str]:
    """Imports absolus de ``archlux.*`` et de ``torch``, y compris sous TYPE_CHECKING."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    trouves: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
            trouves.add(noeud.module)
    return trouves


@pytest.mark.parametrize("fichier", _modules(), ids=_chemin_module)
def test_les_couches_respectent_les_dependances(fichier: Path) -> None:
    """Aucun module n'importe une couche que `ARCHITECTURE.md` §5 lui interdit."""
    paquet = _paquet(fichier)
    autorise = AUTORISE[paquet]
    exemptions = EXEMPTIONS.get(paquet, frozenset())
    for cible in sorted(_imports(fichier)):
        if cible == "archlux":
            # `from archlux import X` runs `archlux/__init__.py`, which loads `api` and
            # the whole legalization chain. No internal module may do that: the version
            # comes from `archlux._version`.
            raise AssertionError(
                f"{_chemin_module(fichier)} imports the root package `archlux`: "
                "forbidden inside the library (import the precise module instead)."
            )
        if not cible.startswith("archlux.") or cible in exemptions:
            continue
        reste = cible.removeprefix("archlux.")
        if reste in LEAVES:
            continue  # dependency-free leaves, importable by every layer
        paquet_cible = reste.split(".")[0]
        if paquet_cible == paquet:
            continue  # import interne au paquet
        ok = paquet_cible in autorise or any(
            reste == permis or reste.startswith(permis + ".") for permis in autorise
        )
        assert ok, (
            f"{_chemin_module(fichier)} importe {cible} : interdit. "
            f"Couches autorisées pour '{paquet}' : {sorted(autorise)}."
        )


@pytest.mark.parametrize("fichier", _modules(), ids=_chemin_module)
def test_le_noyau_ne_reference_pas_torch(fichier: Path) -> None:
    """Seul ``light.appris`` peut nommer ``torch``."""
    module = _chemin_module(fichier)
    reference = any(c == "torch" or c.startswith("torch.") for c in _imports(fichier))
    assert not reference or module in TORCH_TOLERE, f"{module} référence torch"


def test_lmo_n_importe_jamais_light() -> None:
    """L'oracle ignore d'où vient ``c`` — c'est le cœur de l'architecture."""
    for fichier in _modules():
        if _paquet(fichier) != "lmo":
            continue
        assert not any(c.startswith("archlux.light") for c in _imports(fichier)), (
            f"{_chemin_module(fichier)} importe light"
        )


def test_solve_ne_depend_que_du_protocole_light() -> None:
    """``solve`` ne connaît aucune implémentation concrète de substitut."""
    for fichier in _modules():
        if _paquet(fichier) != "solve":
            continue
        for cible in _imports(fichier):
            if cible.startswith("archlux.light"):
                assert cible == "archlux.light.protocole", (
                    f"{_chemin_module(fichier)} importe {cible} ; "
                    "seul archlux.light.protocole est autorisé"
                )


def test_personne_n_importe_bench() -> None:
    """``bench`` est une feuille de l'arbre de dépendances."""
    for fichier in _modules():
        if _paquet(fichier) == "bench":
            continue
        assert not any(c.startswith("archlux.bench") for c in _imports(fichier)), (
            f"{_chemin_module(fichier)} importe bench"
        )


def test_le_noyau_n_importe_pas_torch() -> None:
    """``import archlux`` ne doit charger ``torch`` dans aucun cas (`ARCHITECTURE.md` §5)."""
    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_les_exemptions_restent_rares_et_nommees() -> None:
    """Une dérogation non listée ici n'existe pas ; la liste doit rester courte.

    Ce test n'a l'air de rien : il empêche la liste d'exemptions de devenir le trou par
    lequel la règle de couches se vide, une entrée à la fois.
    """
    total = sum(len(v) for v in EXEMPTIONS.values())
    assert total <= 2, "toute nouvelle dérogation exige une ADR dans le blueprint"


@pytest.mark.parametrize("leaf", sorted(LEAVES))
def test_leaves_import_nothing_else(leaf: str) -> None:
    """A leaf may be imported by every layer only because it depends on nothing."""
    arbre = ast.parse((RACINE / f"{leaf}.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            imported.add((noeud.module or "").split(".")[0])
    assert imported <= LEAVES[leaf], f"{leaf} imports {sorted(imported - LEAVES[leaf])}"


@pytest.mark.parametrize("fichier", _modules(), ids=_chemin_module)
def test_no_relative_imports(fichier: Path) -> None:
    """Relative imports escape the layer check above, which only reads absolute ones."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    relative = [n.lineno for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.level]
    assert not relative, f"{_chemin_module(fichier)}: relative imports at lines {relative}"
