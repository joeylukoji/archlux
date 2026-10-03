"""Evaluation protocol: frozen splits, explicit seeds, raw results.

Nothing imports ``bench``: it is the leaf of the dependency tree
(`ARCHITECTURE.md` §5). An import of ``bench`` from the core fails CI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archlux._deprecation import Alias, lazy_aliases
from archlux.data.splits import Split, load_split
from archlux.errors import InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from archlux.light.protocol import Surrogate
    from archlux.types import Plan

__all__ = ["Split", "compare", "load_split"]


def compare(
    *,
    plans: Sequence[Plan],
    methods: Sequence[Surrogate],
    evaluate_by: Callable[[Plan, Surrogate], float],
) -> tuple[float, ...]:
    """Compare surrogates with a mandatory **external** evaluator.

    Evaluating a network by the network itself is a circular error
    (`MILESTONE-4.md` §8). ``evaluate_by`` is typically the frozen oracle.
    **No default**: omitting the argument raises ``TypeError``.

    ``Surrogate`` is vectorial: the callback must turn the ``Plan`` into a vector
    ``(x, y, w, h)`` (see :func:`archlux.light.tokens.plan_to_vector`) before
    calling ``evaluate``.

    **Known limitation**: the returned value is a **bare** mean, without an
    interval, which `ARCHITECTURE.md` §7 and §10 forbid for a published metric.
    Use :func:`archlux.bench.report.report` (stratified, bootstrap) for any paper
    table; ``compare`` only serves to roughly rank surrogates.

    Raises
    ------
    TypeError
        ``evaluate_by`` missing.
    InvariantViolation
        ``plans`` empty. An empty sample has no mean score: returning ``0.0`` would
        fabricate a measurement and pass a surrogate off as the worst of all.
    """
    if not plans:
        raise InvariantViolation(("empty plans: no mean to compute",))
    return tuple(
        sum(float(evaluate_by(plan, method)) for plan in plans) / len(plans) for method in methods
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "Decoupage": Alias(Split, "archlux.bench.protocol.Split"),
        "charger_decoupage": Alias(load_split, "archlux.bench.protocol.load_split"),
    },
)
