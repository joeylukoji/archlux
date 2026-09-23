"""Banc d'essai — `MILESTONE-6.md` §5 : manifeste, evaluate_by, bruts avant agrégats."""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.bench import compare, report, run
from archlux.bench.stats import bootstrap_apparie, puissance, tost
from archlux.light.analytique import SubstitutAnalytique
from archlux.types import ModeleTrace, Orientation, Piece, Plan


def _plan() -> Plan:
    return Plan(
        pieces=(Piece("a", "sejour", 0.0, 0.0, 6.0, 9.0),),
        murs=(),
        ouvertures=(),
        contour=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    )


def _evaluateur(plan: Plan, methode: object) -> float:
    _ = methode
    return float(sum(p.w * p.h for p in plan.pieces))


def test_manifeste_complet(tmp_path: Path) -> None:
    """`MILESTONE-6.md` §5 : run écrit un manifeste avec poids et calibration_n."""
    modele = ModeleTrace(poids="sha256:abc", calibration_n=40, alpha=0.10)
    resultat = run(
        plans=(_plan(), _plan()),
        orientations=(Orientation(0.0), Orientation(45.0)),
        methods=(SubstitutAnalytique(),),
        evaluate_by=_evaluateur,
        seed=17,
        empreinte_donnees="sha256:donnees",
        decoupage="splits/v2",
        modele=modele,
        repertoire=tmp_path,
    )
    m = resultat.manifest
    assert m.modele is not None
    assert m.modele["poids"] and m.modele["calibration_n"] > 0
    assert resultat.chemin_manifeste.is_file()
    assert resultat.chemin_bruts.is_file()
    # bruts écrits avant tout agrégat : le fichier existe dès le retour de run
    assert len(resultat.lignes) == 2


def test_evaluate_by_obligatoire() -> None:
    """`MILESTONE-6.md` §5 : compare refuse sans évaluateur externe."""
    with pytest.raises(TypeError):
        compare(plans=(_plan(),), methods=(SubstitutAnalytique(),))


def test_report_strate_par_orientation(tmp_path: Path) -> None:
    modele = ModeleTrace(poids="sha256:x", calibration_n=10, alpha=0.1)
    resultat = run(
        plans=(_plan(), _plan(), _plan(), _plan()),
        orientations=(
            Orientation(0.0),
            Orientation(10.0),
            Orientation(180.0),
            Orientation(190.0),
        ),
        methods=(SubstitutAnalytique(),),
        evaluate_by=_evaluateur,
        seed=3,
        empreinte_donnees="d",
        decoupage="s",
        modele=modele,
        repertoire=tmp_path,
    )
    rapport = report(resultat, seed=3)
    assert len(rapport.strates) == 8
    assert sum(s.n for s in rapport.strates) == 4


def test_bootstrap_tost_puissance() -> None:
    a = (1.0, 1.1, 0.9, 1.05)
    b = (0.95, 1.0, 0.85, 1.0)
    ic = bootstrap_apparie(a, b, seed=17, n_replications=199)
    assert ic.bas <= ic.valeur <= ic.haut
    ok, p = tost(a, b, delta=0.5, alpha=0.05)
    assert isinstance(ok, bool)
    assert 0.0 <= p <= 1.0
    assert 0.0 <= puissance(0.5, 1.0, n=30, alpha=0.05) <= 1.0
