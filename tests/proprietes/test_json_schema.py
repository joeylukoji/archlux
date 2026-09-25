"""The published JSON schema v1 and the round trip of real outputs (PLAN.md phase 2, J1).

Milestone 1 was accepted on ``depuis_dict(vers_dict(p)) == p`` for arbitrary plans
(``test_json_io.py``). Its review replays it on what the library writes since phase 1:
legalized plans under load-bearing walls, with a performance bound that states its
regime. It also checks the published schema (``archlux/io/plan-v1.schema.json``)
against the writer and the reader, so that a third party can validate a file without
running archlux.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np
import pytest
from hypothesis import given, settings

import archlux
from archlux.erreurs import ArchluxError, InvariantViole
from archlux.io.json_io import VERSION_SCHEMA, depuis_dict, vers_dict
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.types import Contexte, Plan
from archlux.uq.conforme import CalibrateurConforme, Calibration
from tests.proprietes.strategies import plans_quelconques, realistic_scenarios


def _schema() -> dict[str, Any]:
    text = resources.files("archlux.io").joinpath("plan-v1.schema.json").read_text("utf-8")
    return json.loads(text)  # type: ignore[no-any-return]


VALIDATOR = jsonschema.Draft202012Validator(_schema())


def _errors(document: dict[str, Any]) -> list[str]:
    return [error.message for error in VALIDATOR.iter_errors(document)]


def test_the_schema_is_a_valid_draft_2020_12_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(_schema())
    assert _schema()["properties"]["schema"]["const"] == VERSION_SCHEMA


def test_the_schema_is_shipped_with_the_package() -> None:
    """A file in the source tree only would not reach a ``pip install``."""
    assert resources.files("archlux.io").joinpath("plan-v1.schema.json").is_file()


@given(plan=plans_quelconques())
@settings(max_examples=200, deadline=None)
def test_every_written_plan_matches_the_schema(plan: Plan) -> None:
    assert _errors(vers_dict(plan)) == []


def _calibration() -> Calibration:
    rng = np.random.default_rng(5)
    predictions = rng.normal(50.0, 5.0, 60)
    calibrator = CalibrateurConforme(indicateur="sDA")
    calibrator.ajuster(predictions, predictions + rng.normal(0.0, 1.0, 60), np.ones(60))
    return calibrator.snapshot()


def _outputs(plan: Plan, ctx: Contexte) -> list[Plan]:
    """What legalize writes: classic, and performance with a bound in regime "selected"."""
    outputs = []
    for kwargs in (
        {},
        {
            "objective": Daylight(SubstitutAnalytique(), q_chapeau=1.0),
            "calibration": _calibration(),
        },
    ):
        try:
            outputs.append(archlux.legalize(plan, ctx, **kwargs))  # type: ignore[arg-type]
        except ArchluxError:
            continue  # a refusal writes nothing
    return outputs


@given(scenario=realistic_scenarios())
@settings(max_examples=40, deadline=None, derandomize=True)
def test_legalized_plans_round_trip_through_a_file(
    scenario: tuple[Plan, Contexte], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Load-bearing walls, certificate and regime survive ``to_json`` / ``from_json``."""
    plan, ctx = scenario
    for output in _outputs(plan, ctx):
        path = tmp_path_factory.mktemp("j1") / "plan.json"
        output.to_json(path)
        assert _errors(json.loads(path.read_text("utf-8"))) == []
        back = Plan.from_json(path)
        assert back == output
        assert back.certificat is not None
        if back.certificat.performance is not None:
            assert back.certificat.performance.regime == "selected"


def test_a_performance_output_carries_its_regime_in_the_file(tmp_path: Path) -> None:
    """At least one scenario produces a bound: the loop above is not vacuous."""
    plan, ctx = _a_scenario()
    (output,) = [o for o in _outputs(plan, ctx) if o.certificat and o.certificat.performance]
    output.to_json(tmp_path / "plan.json")
    document = json.loads((tmp_path / "plan.json").read_text("utf-8"))
    assert document["certificat"]["performance"]["regime"] == "selected"
    assert any(wall["porteur"] for wall in document["murs"]) or ctx.structure.murs_porteurs


def _a_scenario() -> tuple[Plan, Contexte]:
    from dataclasses import replace

    from archlux.types import Mur, Piece, Referentiel, Structure
    from tests.proprietes.strategies import CONTEXTE_DEFAUT

    wall = Mur(id="lb", a=(6.0, 0.0), b=(6.0, 9.0), porteur=True)
    ctx = replace(
        CONTEXTE_DEFAUT,
        structure=Structure(murs_porteurs=(wall,)),
        referentiel=Referentiel(aires_min=(("chambre", 20.0),), largeur_min=1.0),
    )
    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(wall,),
        ouvertures=(),
        contour=ctx.contour,
    )
    return plan, ctx


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("pieces", 0, "w"), 0.0),
        (("murs", 0, "epaisseur"), 0.0),
        (("schema",), "2"),
    ],
)
def test_the_schema_and_the_reader_refuse_the_same_values(
    path: tuple[str | int, ...], value: object
) -> None:
    document = vers_dict(_a_scenario()[0])
    node: Any = document
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert _errors(document)
    with pytest.raises(InvariantViole):
        depuis_dict(document)


def test_the_schema_refuses_a_bound_without_regime() -> None:
    """Batch 1.6: a bound whose regime is unknown is never read as "exchangeable"."""
    plan, ctx = _a_scenario()
    (output,) = [o for o in _outputs(plan, ctx) if o.certificat and o.certificat.performance]
    document = vers_dict(output)
    del document["certificat"]["performance"]["regime"]
    assert _errors(document)
    with pytest.raises(InvariantViole, match="regime"):
        depuis_dict(document)
