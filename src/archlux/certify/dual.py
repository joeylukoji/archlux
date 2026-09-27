"""Translation of dual prices into the language of an architect.

A raw dual price is "the number of row 47". Crossed with ``Polytope.origins`` it becomes
"load-bearing wall p1 at x = 6 m: relaxing it by 10 cm would change the total displacement
by -0.20 m". That translation is the main usable output of the certificate: it says
**which constraint to relax**.

Two things are done here and nowhere else (PLAN.md 3.12):

- **filtering**: the rows of the L1 epigraph (``ecart plus/moins ...``) are solver
  artefacts, not constraints of the brief, so they are never reported;
- **units**: a price is the change of the objective per metre of relaxation. It is
  reported for a step of ``step_m`` metres, in the unit of the objective: metres of total
  displacement in classic mode, points of the indicator in performance mode (a
  *prediction* of the surrogate there, and the phrase says so).

Prices are valid **locally** (a few tens of centimetres). A diagnostic without that
interval would mislead.
"""

from __future__ import annotations

import re

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.arrays import VecteurF
from archlux.geom.polytope import Polytope

__all__ = ["describe_origin", "translate_duals"]

_VALIDITY = "valid for small changes only, a few tens of cm"

_WALL = re.compile(
    r"^load-bearing (?P<wall>\S+): (?P<room>\S+) (?P<side>left|right|below|above) "
    r"of (?P<bound>\S+)$"
)
_SEPARATION = re.compile(r"^separation (?P<axis>horizontale|verticale) (?P<a>[^|\s]+)\|(?P<b>\S+)$")
_OUTLINE = re.compile(r"^contour (?P<side>droit|haut) (?P<room>\S+)$")
_AREA = re.compile(r"^(?:surface (?P<room_fr>\S+)|minimum area (?P<room_en>[^:\s]+)(?::.*)?)$")

_SIDE_OF_WALL = {
    "left": ("x", "stays to the left of"),
    "right": ("x", "stays to the right of"),
    "below": ("y", "stays below"),
    "above": ("y", "stays above"),
}


def describe_origin(label: str) -> str | None:
    """Business wording of the label of a polytope row.

    Parameters
    ----------
    label : str
        An entry of ``Polytope.origins``.

    Returns
    -------
    str or None
        A sentence fragment naming the constraint, or ``None`` for a solver artefact (a
        row of the L1 epigraph) that must not be reported. A label that is not
        recognised is returned unchanged: showing it is better than hiding a constraint.
    """
    if label.startswith("ecart "):
        return None
    if wall := _WALL.match(label):
        coordinate, verb = _SIDE_OF_WALL[wall["side"]]
        return (
            f"load-bearing wall {wall['wall']} at {coordinate} = {wall['bound']} m: "
            f"room {wall['room']} {verb} it"
        )
    if separation := _SEPARATION.match(label):
        relation = "left of" if separation["axis"] == "horizontale" else "below"
        return f"room {separation['a']} stays {relation} room {separation['b']}"
    if outline := _OUTLINE.match(label):
        side = "right" if outline["side"] == "droit" else "top"
        return f"{side} side of the outline limits room {outline['room']}"
    if area := _AREA.match(label):
        return f"minimum area of room {area['room_fr'] or area['room_en']}"
    return label


def _sentence(description: str, price: float, *, objective: str, step_m: float) -> str:
    """One phrase: what is relaxed, by how much, and the effect in the objective's unit."""
    step = f"{step_m * 100.0:g} cm"
    if objective == "displacement":
        effect = f"would change the total displacement by {price * step_m:+.2f} m"
    else:
        # The performance objective is minus the surrogate: a negative price is a gain.
        effect = (
            f"would change the predicted {objective} by {-price * step_m:+.2f} "
            "(surrogate prediction, not a guarantee)"
        )
    return f"{description}: relaxing it by {step} {effect} ({_VALIDITY})"


def translate_duals(
    duals: VecteurF,
    poly: Polytope,
    *,
    threshold: float = 1e-6,
    n_max: int = 10,
    objective: str = "displacement",
    step_m: float = 0.10,
) -> tuple[tuple[str, float], ...]:
    """Pair every non-zero dual price with the business wording of its constraint.

    Parameters
    ----------
    duaux : numpy.ndarray
        Dual prices, in the order of the rows of ``poly.A``.
    poly : Polytope
        Provides ``origines``, indispensable and not reconstructible afterwards.
    seuil : float, optional
        Below it the constraint is inactive and is not reported.
    n_max : int, optional
        Number of constraints reported, the costliest first.
    objective : str, optional
        What the prices are about: ``"displacement"`` (classic mode, metres of total
        displacement) or the name of an indicator (``"sDA"``...) in performance mode,
        where the price is a change of the *predicted* indicator.
    step_m : float, optional
        Size of the relaxation the phrases speak about, in metres (default 10 cm).

    Returns
    -------
    tuple of (str, float)
        Pairs ``(readable phrase, raw price)``, sorted by decreasing absolute price. The
        raw price is the change of the objective per metre of relaxation; the phrase
        gives the change for ``step_m`` and states its local validity. Rows of the L1
        epigraph are never reported.
    """
    vector = np.asarray(duals, dtype=float).ravel()
    pairs: list[tuple[str, float]] = []
    for label, raw in zip(poly.origins, vector, strict=True):
        price = float(raw)
        description = describe_origin(label)
        if abs(price) <= threshold or description is None:
            continue
        pairs.append((_sentence(description, price, objective=objective, step_m=step_m), price))
    pairs.sort(key=lambda pair: -abs(pair[1]))
    return tuple(pairs[:n_max])


__getattr__ = lazy_aliases(
    __name__,
    {
        "traduire_duaux": Alias(translate_duals, "archlux.certify.dual.translate_duals"),
    },
)
