"""The dual diagnostic speaks in business terms and units (PLAN.md 3.12).

Before, a certificate listed ``ecart plus chambre.x`` with a bare price:
solver rows of the L1 epigraph that are no constraint of the brief, raw internal labels,
and a price with no unit.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from archlux import Context, Orientation, Plan, Regulation, Room, Structure, Wall, legalize
from archlux.certify.dual import describe_origin, translate_duals
from archlux.geom.polytope import Polytope


def polytope(labels: tuple[str, ...]) -> Polytope:
    n = len(labels)
    return Polytope(
        A=sparse.csr_matrix(np.eye(n)),
        b=np.ones(n),
        A_eq=sparse.csr_matrix((0, n)),
        b_eq=np.zeros(0),
        bounds=((0.0, 1.0),) * n,
        index={f"v{k}": k for k in range(n)},
        origins=labels,
    )


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("load-bearing p1: chambre right of 6", ["load-bearing wall p1", "chambre", "x = 6"]),
        ("load-bearing p2: sdb below of 3.5", ["load-bearing wall p2", "sdb", "y = 3.5"]),
        ("separation horizontale a|b", ["a", "left of", "b"]),
        ("separation verticale a|b", ["a", "below", "b"]),
        ("contour droit sejour", ["outline", "sejour"]),
        ("contour haut sejour", ["outline", "sejour"]),
        ("surface cuisine", ["minimum area", "cuisine"]),
        ("minimum area cuisine: chord 3", ["minimum area", "cuisine"]),
    ],
)
def test_known_labels_are_described_in_business_terms(label: str, expected: list[str]) -> None:
    text = describe_origin(label)
    assert text is not None
    for part in expected:
        assert part in text
    assert "chord" not in text


def test_epigraph_rows_are_solver_artefacts() -> None:
    assert describe_origin("ecart plus chambre.x") is None
    assert describe_origin("ecart moins sejour.w") is None


def test_an_unknown_label_is_kept_as_is() -> None:
    assert describe_origin("mur porteur axe 3") == "mur porteur axe 3"


def test_epigraph_rows_never_reach_the_diagnostic() -> None:
    poly = polytope(("ecart plus a.x", "separation horizontale a|b"))
    phrases = translate_duals(np.array([-9.0, -1.0]), poly)
    assert len(phrases) == 1
    assert "ecart" not in phrases[0][0]


def test_the_price_is_converted_to_the_displacement_of_a_step() -> None:
    poly = polytope(("load-bearing p1: chambre right of 6",))
    ((phrase, price),) = translate_duals(np.array([-2.0]), poly)
    assert price == -2.0
    assert "10 cm" in phrase
    assert "-0.20 m" in phrase
    assert "total displacement" in phrase


def test_the_step_is_configurable() -> None:
    poly = polytope(("load-bearing p1: chambre right of 6",))
    ((phrase, _),) = translate_duals(np.array([-2.0]), poly, step_m=0.5)
    assert "50 cm" in phrase
    assert "-1.00 m" in phrase


def test_an_indicator_objective_is_reported_as_a_gain_of_that_indicator() -> None:
    """The objective of the performance mode is minus the surrogate: a negative price is a gain."""
    poly = polytope(("load-bearing p1: chambre right of 6",))
    ((phrase, _),) = translate_duals(np.array([-2.0]), poly, objective="sDA")
    assert "sDA" in phrase
    assert "+0.20" in phrase
    assert "surrogate" in phrase
    assert "displacement" not in phrase


def test_every_phrase_states_its_local_validity() -> None:
    poly = polytope(("separation horizontale a|b", "mur porteur axe 3"))
    for phrase, _ in translate_duals(np.array([-1.0, -2.0]), poly):
        assert "small changes" in phrase


def test_a_real_certificate_lists_only_business_constraints() -> None:
    outline = ((0.0, 0.0), (10.0, 0.0), (10.0, 7.0), (0.0, 7.0))
    plan = Plan(
        rooms=(
            Room(id="sejour", type="sejour", x=0.0, y=0.0, w=6.2, h=7.0),
            Room(id="chambre", type="chambre", x=6.0, y=0.0, w=4.0, h=4.0),
            Room(id="sdb", type="sdb", x=6.0, y=4.0, w=4.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=outline,
    )
    wall = Wall(id="p1", a=(6.0, 0.0), b=(6.0, 7.0), load_bearing=True)
    ctx = Context(
        structure=Structure(load_bearing_walls=(wall,)),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=1.5),
    )
    duals = legalize(plan, ctx, tiling=True).certificate.duals  # type: ignore[union-attr]
    assert duals
    assert not any("ecart" in phrase for phrase, _ in duals)
    assert any("load-bearing wall p1" in phrase for phrase, _ in duals)
    assert all("total displacement" in phrase for phrase, _ in duals)


def test_performance_mode_prices_are_reported_in_indicator_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Frank-Wolfe pass minimizes minus the surrogate: its prices are not metres."""
    import archlux.api as api

    seen: list[str] = []
    original = api.translate_duals

    def spy(*args: object, **kwargs: object) -> object:
        seen.append(str(kwargs.get("objective")))
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(api, "translate_duals", spy)
    from archlux.light.analytique import AnalyticSurrogate

    outline = ((0.0, 0.0), (10.0, 0.0), (10.0, 7.0), (0.0, 7.0))
    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=5.0, h=7.0),
            Room(id="b", type="sejour", x=5.0, y=0.0, w=5.0, h=7.0),
        ),
        walls=(),
        openings=(),
        outline=outline,
    )
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=1.0),
    )
    surrogate = AnalyticSurrogate()
    legalize(plan, ctx, objective=surrogate)
    assert "displacement" in seen
    assert surrogate.indicator in seen
