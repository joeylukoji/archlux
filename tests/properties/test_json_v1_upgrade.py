"""Schema v1 files are still read, through an explicit upgrade to v2 (PLAN.md 3.9, wave 4).

The v1 document below is written by hand, key by key, from the published v1 schema:
it is independent of what the writer emits today, so it keeps testing the old format.
"""

from __future__ import annotations

import copy
import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from archlux import InvariantViolation, Plan
from archlux.io.json_io import from_dict, to_dict, upgrade_v1

V1: dict[str, Any] = {
    "schema": "1",
    "contour": [[0.0, 0.0], [12.0, 0.0], [12.0, 9.0], [0.0, 9.0]],
    "pieces": [
        {"id": "a", "type": "sejour", "x": 0.0, "y": 0.0, "w": 6.0, "h": 9.0},
        {"id": "b", "type": "chambre", "x": 6.0, "y": 0.0, "w": 6.0, "h": 9.0},
        {"id": "c", "type": "office", "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
    ],
    "murs": [
        {"id": "m", "a": [6.0, 0.0], "b": [6.0, 9.0], "porteur": True, "epaisseur": 0.2},
    ],
    "ouvertures": [
        {
            "id": "f",
            "mur_id": "m",
            "s": 0.5,
            "largeur_rel": 0.25,
            "hauteur_allege": 1.0,
            "hauteur_linteau": 2.15,
        }
    ],
    "certificat": {
        "geometrie": {
            "valide": True,
            "chevauchement": False,
            "jours": False,
            "surfaces_ok": True,
            "structure_preservee": True,
            "deplacement_max": 0.21,
            "violations": [],
        },
        "performance": {
            "indicateur": "sDA",
            "valeur": 56.2,
            "borne_inf": 51.4,
            "borne_sup": 61.0,
            "couverture": 0.9,
            "n_calibration": 1284,
            "regime": "selected",
        },
        "duaux": [["mur porteur axe 3", -4.1]],
        "manifeste": {
            "version": "0.4.0",
            "horodatage": "2026-09-09T00:00:00Z",
            "graine": 17,
            "empreinte_donnees": "abc",
            "decoupage": None,
            "environnement": [["python", "3.13"]],
            "parametres": [["alpha", "0.1"]],
            "modele": {"poids": "deadbeef", "calibration_n": 1284, "alpha": 0.1},
        },
    },
}


def schema(version: str) -> jsonschema.Draft202012Validator:
    text = resources.files("archlux.io").joinpath(f"plan-v{version}.schema.json").read_text("utf-8")
    return jsonschema.Draft202012Validator(json.loads(text))


def test_the_hand_written_v1_document_matches_the_v1_schema() -> None:
    assert list(schema("1").iter_errors(V1)) == []


def test_the_upgraded_document_matches_the_v2_schema() -> None:
    assert [e.message for e in schema("2").iter_errors(upgrade_v1(V1))] == []


def test_the_reader_gives_the_same_plan_for_v1_and_its_upgrade() -> None:
    assert from_dict(V1) == from_dict(upgrade_v1(V1))


def test_the_upgrade_translates_keys_and_room_types() -> None:
    plan = from_dict(V1)
    assert [room.type for room in plan.rooms] == ["living_room", "bedroom", "office"]
    assert plan.walls[0].load_bearing is True
    assert plan.openings[0].wall_id == "m"
    assert plan.certificate is not None
    assert plan.certificate.geometry.max_displacement == 0.21
    assert plan.certificate.performance is not None
    assert plan.certificate.performance.regime == "selected"
    assert plan.certificate.manifest is not None
    assert plan.certificate.manifest.model is not None
    assert plan.certificate.manifest.model.weights_fingerprint == "deadbeef"
    assert plan.certificate.duals == (("mur porteur axe 3", -4.1),)


def test_the_upgrade_does_not_modify_its_input() -> None:
    before = copy.deepcopy(V1)
    upgrade_v1(V1)
    assert before == V1


def test_the_writer_emits_v2_only() -> None:
    document = to_dict(from_dict(V1))
    assert document["schema"] == "2"
    assert "pieces" not in document
    assert [room["type"] for room in document["rooms"]] == ["living_room", "bedroom", "office"]
    assert [e.message for e in schema("2").iter_errors(document)] == []


def test_a_v1_file_becomes_a_v2_file_with_the_same_plan(tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    old.write_text(json.dumps(V1), encoding="utf-8")
    plan = Plan.from_json(old)
    new = tmp_path / "new.json"
    plan.to_json(new)
    assert json.loads(new.read_text(encoding="utf-8"))["schema"] == "2"
    assert Plan.from_json(new) == plan


def test_an_unknown_schema_is_refused_and_says_what_is_accepted() -> None:
    document = copy.deepcopy(V1)
    document["schema"] = "3"
    with pytest.raises(InvariantViolation, match="'2' or '1'"):
        from_dict(document)


def test_a_malformed_v1_document_is_reported_by_the_reader() -> None:
    document = copy.deepcopy(V1)
    del document["pieces"][0]["w"]
    with pytest.raises(InvariantViolation, match="invalid JSON structure"):
        from_dict(document)
