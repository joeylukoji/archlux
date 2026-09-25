"""Lazy deprecated aliases for renamed public names (ADR 0001, PLAN.md 3.9).

French public names stay importable until 1.0.0 and emit a ``DeprecationWarning``. Each
module that renamed something used to carry its own copy of that logic, with slightly
different messages. This leaf builds the module-level ``__getattr__`` once::

    __getattr__ = lazy_aliases(__name__, {"OldName": Alias(NewName, "archlux.mod.NewName")})

Behaviour, identical to the copies it replaces: the warning is attributed to the caller;
``from module import OldName`` warns once (the import machinery probes with ``hasattr``
first); any other name raises ``AttributeError``. Aliases are not listed in ``__all__``.

A leaf: it imports nothing from archlux, so every layer may use it.
"""

from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ["Alias", "lazy_aliases"]


@dataclass(frozen=True, slots=True)
class Alias:
    """A deprecated name: what it resolves to, and what to use instead.

    Parameters
    ----------
    value : object
        The object the old name still returns (the renamed class, function, constant).
    replacement : str
        The new name, as written in the warning ("use ...").
    note : str, optional
        One sentence of context appended to the warning, for a rename that also
        corrects a claim (for instance "not a simulation").
    """

    value: object
    replacement: str
    note: str = ""


def lazy_aliases(module_name: str, aliases: Mapping[str, Alias]) -> Callable[[str], object]:
    """Build the module ``__getattr__`` that serves ``aliases`` with a warning.

    Parameters
    ----------
    module_name : str
        ``__name__`` of the module, used in the message and in ``AttributeError``.
    aliases : mapping of str to Alias
        Old name to its :class:`Alias`.

    Returns
    -------
    callable
        A function to assign to ``__getattr__`` at module level.
    """

    def __getattr__(name: str) -> object:
        alias = aliases.get(name)
        if alias is None:
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
        if sys._getframe(1).f_code.co_filename.startswith("<frozen importlib"):
            # `from module import name` probes with hasattr first: warn only once.
            return alias.value
        note = f": {alias.note}" if alias.note else ""
        warnings.warn(
            f"{module_name}.{name} is deprecated, use {alias.replacement}{note} (ADR 0001)",
            DeprecationWarning,
            stacklevel=2,
        )
        return alias.value

    return __getattr__
