"""A probabilistic bound states its regime (PLAN.md batch 1.6, AUDIT.md §5.3).

A conformal coverage holds for a plan exchangeable with the calibration set. A plan
chosen by the optimizer is not: it sits where the surrogate overestimates (winner's
curse). The certificate must say which case it is in, and never print a coverage it
cannot keep.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

import archlux
from archlux.erreurs import Infaisable, InvariantViole
from archlux.io.json_io import depuis_dict, vers_dict
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.light.protocole import point_prediction
from archlux.types import BornePerformance, Certificat, PreuveGeometrique, Referentiel
from archlux.uq.conforme import CalibrateurConforme, Calibration, borner, dataset_fingerprint
from tests.proprietes.strategies import CONTEXTE_DEFAUT


def _bound(**changes: object) -> BornePerformance:
    fields: dict[str, object] = {
        "indicateur": "sDA",
        "valeur": 56.2,
        "borne_inf": 51.4,
        "borne_sup": 61.0,
        "couverture": 0.90,
        "n_calibration": 1284,
        "regime": "exchangeable",
    }
    fields.update(changes)
    return BornePerformance(**fields)  # type: ignore[arg-type]


def _proof() -> PreuveGeometrique:
    return PreuveGeometrique(
        valide=True,
        chevauchement=False,
        jours=False,
        surfaces_ok=True,
        structure_preservee=True,
        deplacement_max=0.0,
    )


def _calibration(indicator: str = "sDA", n: int = 60) -> Calibration:
    rng = np.random.default_rng(5)
    predictions = rng.normal(50.0, 5.0, n)
    truths = predictions + rng.normal(0.0, 1.0, n)
    calibrator = CalibrateurConforme(indicateur=indicator)  # type: ignore[arg-type]
    calibrator.ajuster(predictions, truths, np.ones(n), alpha=0.10)
    return calibrator.snapshot()


# --- The type -------------------------------------------------------------------------


def test_a_bound_without_regime_cannot_be_built() -> None:
    with pytest.raises(TypeError, match="regime"):
        BornePerformance(  # type: ignore[call-arg]
            indicateur="sDA",
            valeur=56.2,
            borne_inf=51.4,
            borne_sup=61.0,
            couverture=0.90,
            n_calibration=10,
        )


def test_an_unknown_regime_is_refused() -> None:
    with pytest.raises(InvariantViole, match="regime"):
        _bound(regime="hopeful")


def test_an_inverted_interval_is_refused() -> None:
    with pytest.raises(InvariantViole, match="inverted"):
        _bound(borne_inf=62.0)


def test_only_an_exchangeable_plan_has_a_guaranteed_coverage() -> None:
    assert _bound().coverage_guaranteed
    assert not _bound(regime="selected").coverage_guaranteed


# --- The report -----------------------------------------------------------------------


def test_the_report_claims_the_coverage_of_an_exchangeable_plan() -> None:
    text = Certificat(geometrie=_proof(), performance=_bound()).rapport()
    assert "[PREDICTION — couverture 90 %]" in text


def test_the_report_never_claims_the_coverage_of_a_selected_plan() -> None:
    text = Certificat(geometrie=_proof(), performance=_bound(regime="selected")).rapport()
    assert "couverture 90 %]" not in text
    assert "couverture NON garantie" in text
    assert "oracle" in text


# --- Mandatory arguments ----------------------------------------------------------------


def test_the_uncertainty_scale_is_mandatory() -> None:
    """The former default ``incertitude=1.0`` was wrong for normalized scores."""
    with pytest.raises(TypeError):
        borner(50.0, _calibration(), regime="exchangeable")  # type: ignore[call-arg]


def test_the_regime_is_mandatory() -> None:
    with pytest.raises(TypeError):
        borner(50.0, _calibration(), incertitude=1.0)  # type: ignore[call-arg]


# --- The fingerprint ----------------------------------------------------------------------


def test_the_fingerprint_identifies_the_data_set_not_the_scores() -> None:
    """Shifting predictions and truths together keeps every score, not the data set."""
    rng = np.random.default_rng(1)
    predictions = rng.normal(50.0, 5.0, 30)
    truths = predictions + rng.normal(0.0, 1.0, 30)
    sigma = np.ones(30)
    first, second = CalibrateurConforme(), CalibrateurConforme()
    first.ajuster(predictions, truths, sigma)
    second.ajuster(predictions + 10.0, truths + 10.0, sigma)
    assert first.scores is not None and second.scores is not None
    assert np.allclose(first.scores, second.scores)
    assert first.empreinte_jeu != second.empreinte_jeu


def test_the_fingerprint_is_deterministic_and_column_aware() -> None:
    a, b, c = np.arange(5.0), np.arange(5.0) + 1.0, np.ones(5)
    assert dataset_fingerprint(a, b, c) == dataset_fingerprint(a.copy(), b.copy(), c.copy())
    assert dataset_fingerprint(a, b, c) != dataset_fingerprint(b, a, c)


# --- legalize fills the performance, in the selected regime -----------------------------------


def _plan() -> archlux.Plan:
    """Two rooms tiling the default 12 m x 9 m outline, off-centre."""
    return archlux.Plan(
        pieces=(
            archlux.Piece(id="a", type="sejour", x=0.0, y=0.0, w=5.0, h=9.0),
            archlux.Piece(id="b", type="chambre", x=5.0, y=0.0, w=7.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )


def test_legalize_bounds_the_chosen_plan_in_the_selected_regime() -> None:
    plan = _plan()
    surrogate = SubstitutAnalytique()
    objective = Daylight(surrogate, q_chapeau=1.0)
    calibration = _calibration(surrogate.indicateur)
    result = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=objective, calibration=calibration)
    assert result.certificat is not None
    bound = result.certificat.performance
    assert bound is not None
    assert bound.regime == "selected" and not bound.coverage_guaranteed
    assert bound.n_calibration == calibration.n
    # Centred on the surrogate's prediction mu, not on the pessimistic mu - q sigma.
    x = np.array([v for room in result.pieces for v in (room.x, room.y, room.w, room.h)])
    mu, _ = point_prediction(objective, x, CONTEXTE_DEFAUT.orientation)
    assert bound.valeur == pytest.approx(mu, rel=1e-6)
    assert "couverture NON garantie" in result.certificat.rapport()


def test_legalize_without_calibration_claims_no_performance() -> None:
    result = archlux.legalize(
        _plan(), CONTEXTE_DEFAUT, objective=Daylight(SubstitutAnalytique(), q_chapeau=1.0)
    )
    assert result.certificat is not None and result.certificat.performance is None


def test_a_calibration_needs_an_objective() -> None:
    with pytest.raises(ValueError, match="objective"):
        archlux.legalize(_plan(), CONTEXTE_DEFAUT, calibration=_calibration())


def test_a_calibration_of_another_indicator_is_refused() -> None:
    objective = Daylight(SubstitutAnalytique(), q_chapeau=1.0)
    other = "ASE" if objective.indicateur != "ASE" else "sDA"
    with pytest.raises(ValueError, match="cannot bound"):
        archlux.legalize(
            _plan(), CONTEXTE_DEFAUT, objective=objective, calibration=_calibration(other)
        )


# --- Serialization --------------------------------------------------------------------------


def test_the_regime_survives_serialization() -> None:
    certificate = Certificat(geometrie=_proof(), performance=_bound(regime="selected"))
    restored = depuis_dict(vers_dict(replace(_plan(), certificat=certificate)))
    assert restored.certificat is not None and restored.certificat.performance is not None
    assert restored.certificat.performance.regime == "selected"


def test_a_serialized_bound_without_regime_is_refused() -> None:
    certificate = Certificat(geometrie=_proof(), performance=_bound())
    data = vers_dict(replace(_plan(), certificat=certificate))
    del data["certificat"]["performance"]["regime"]
    with pytest.raises(InvariantViole, match="regime"):
        depuis_dict(data)


# --- Review of batch 1.6 ----------------------------------------------------------------------


def test_an_ase_bound_is_published_as_a_positive_glare() -> None:
    """Review C1: surrogates return ASE negated; the certificate reads it positive."""
    surrogate = SubstitutAnalytique(indicateur_vise="ASE")
    calibration = _calibration("ASE")
    result = archlux.legalize(
        _plan(),
        CONTEXTE_DEFAUT,
        objective=Daylight(surrogate, q_chapeau=1.0),
        calibration=calibration,
    )
    assert result.certificat is not None
    bound = result.certificat.performance
    assert bound is not None and bound.indicateur == "ASE"
    x = np.array([v for room in result.pieces for v in (room.x, room.y, room.w, room.h)])
    raw = surrogate.evaluer(x, CONTEXTE_DEFAUT.orientation)
    assert raw < 0.0 < bound.valeur
    assert bound.valeur == pytest.approx(-raw, rel=1e-6)
    assert bound.borne_inf <= bound.valeur <= bound.borne_sup


def test_every_wrapping_layer_is_removed() -> None:
    """Review m2: Daylight(Daylight(s)) must not keep one pessimistic margin."""
    surrogate = SubstitutAnalytique()
    x = np.array([0.0, 0.0, 5.0, 9.0, 5.0, 0.0, 7.0, 9.0])
    orientation = CONTEXTE_DEFAUT.orientation
    nested = Daylight(Daylight(surrogate, q_chapeau=1.0), q_chapeau=2.0)
    assert point_prediction(nested, x, orientation)[0] == pytest.approx(
        surrogate.evaluer(x, orientation)
    )


def test_an_unusable_calibration_is_refused_before_any_solving() -> None:
    """Review m1: a set too small for alpha fails first, not after Frank-Wolfe.

    The plan cannot fit (two rooms at least 2 m wide in a 3 m outline): refusing with
    the calibration error rather than ``Infaisable`` shows nothing was solved.
    """
    small_outline = ((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0))
    tiny_ctx = replace(
        CONTEXTE_DEFAUT,
        contour=small_outline,
        referentiel=Referentiel(aires_min=(), largeur_min=2.0),
    )
    with pytest.raises(Infaisable):
        archlux.legalize(_plan(), tiny_ctx, objective=SubstitutAnalytique())
    too_small = Calibration(scores=np.ones(5), alpha=0.10, indicateur="sDA", empreinte_jeu="x")
    with pytest.raises(InvariantViole, match="trop petit"):
        archlux.legalize(
            _plan(),
            tiny_ctx,
            objective=Daylight(SubstitutAnalytique(), q_chapeau=1.0),
            calibration=too_small,
        )


def test_a_calibration_of_the_wrong_type_is_refused() -> None:
    with pytest.raises(InvariantViole, match="Calibration"):
        archlux.legalize(
            _plan(),
            CONTEXTE_DEFAUT,
            objective=Daylight(SubstitutAnalytique(), q_chapeau=1.0),
            calibration=object(),  # type: ignore[arg-type]
        )


def test_no_uncertainty_at_the_plan_gives_no_bound_not_a_lost_plan() -> None:
    """Review m1: sigma = 0 is only known after solving; keep the proved plan."""
    result = archlux.legalize(
        _plan(),
        CONTEXTE_DEFAUT,
        objective=SubstitutAnalytique(sigma_nominal=0.0),
        calibration=_calibration(),
    )
    assert result.certificat is not None and result.certificat.geometrie.valide
    assert result.certificat.performance is None


def test_the_fingerprint_is_computed_on_the_raw_uncertainties() -> None:
    """Review m3: a third party recomputes it on the published data, before any floor."""
    predictions, truths = np.array([1.0, 2.0]), np.array([1.5, 2.5])
    zero, tiny = CalibrateurConforme(), CalibrateurConforme()
    zero.ajuster(predictions, truths, np.array([0.0, 1.0]), alpha=0.5)
    tiny.ajuster(predictions, truths, np.array([1e-13, 1.0]), alpha=0.5)
    assert zero.empreinte_jeu != tiny.empreinte_jeu
    assert zero.empreinte_jeu == dataset_fingerprint(predictions, truths, np.array([0.0, 1.0]))


@pytest.mark.parametrize("bad", [-1.0, np.nan, np.inf])
def test_a_negative_or_non_finite_uncertainty_is_refused(bad: float) -> None:
    with pytest.raises(InvariantViole, match="uncertainties"):
        CalibrateurConforme().ajuster(np.ones(3), np.ones(3), np.array([1.0, bad, 1.0]))
