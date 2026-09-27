"""Lazy deprecated aliases for renamed public names (ADR 0001, PLAN.md 3.9).

French public names stay importable until 1.0.0 and emit a ``DeprecationWarning``. Each
module that renamed something used to carry its own copy of that logic, with slightly
different messages. This leaf builds the module-level ``__getattr__`` once::

    __getattr__ = lazy_aliases(__name__, {"OldName": Alias(NewName, "archlux.mod.NewName")})

Behaviour, identical to the copies it replaces: the warning is attributed to the caller;
``from module import OldName`` warns once (the import machinery probes with ``hasattr``
first); any other name raises ``AttributeError``. Aliases are not listed in ``__all__``.

Renamed keyword parameters of a public function go through :func:`renamed_parameters`::

    @renamed_parameters({"chemin": "path"})
    def write(plan: Plan, path: str | Path) -> None: ...

A leaf: it imports nothing from archlux, so every layer may use it.
"""

from __future__ import annotations

import functools
import sys
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ["Alias", "lazy_aliases", "renamed_parameters"]

_P = ParamSpec("_P")
_R = TypeVar("_R")


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


def lazy_aliases(
    module_name: str,
    aliases: Mapping[str, Alias],
    *,
    fallback: Callable[[str], object] | None = None,
) -> Callable[[str], object]:
    """Build the module ``__getattr__`` that serves ``aliases`` with a warning.

    Parameters
    ----------
    module_name : str
        ``__name__`` of the module, used in the message and in ``AttributeError``.
    aliases : mapping of str to Alias
        Old name to its :class:`Alias`.
    fallback : callable, optional
        Serves every other name (the module's own lazy attributes). It must raise
        ``AttributeError`` for a name it does not know. Without it, other names raise.

    Returns
    -------
    callable
        A function to assign to ``__getattr__`` at module level.
    """

    def __getattr__(name: str) -> object:
        alias = aliases.get(name)
        if alias is None:
            if fallback is not None:
                return fallback(name)
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


def renamed_parameters(
    renames: Mapping[str, str],
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Accept the old name of renamed keyword parameters, with a ``DeprecationWarning``.

    Parameters
    ----------
    renames : mapping of str to str
        Old keyword to its new name, for instance ``{"chemin": "path"}``. Strings, like
        the keys of :func:`lazy_aliases`, so the old names never appear as identifiers.

    Returns
    -------
    callable
        A decorator. The decorated function keeps its signature (``inspect.signature``
        follows ``__wrapped__``); passing both the old and the new name raises
        ``TypeError``, as passing one argument twice would.

    Examples
    --------
    >>> import warnings
    >>> @renamed_parameters({"chemin": "path"})
    ... def write(path: str) -> str:
    ...     return path
    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter("always")
    ...     write(chemin="plan.json")
    'plan.json'
    >>> str(caught[0].message)
    'write(chemin=...) is deprecated, use path=... (ADR 0001)'
    """

    def decorate(func: Callable[_P, _R]) -> Callable[_P, _R]:
        @functools.wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            if kwargs and not renames.keys().isdisjoint(kwargs):
                for old, new in renames.items():
                    if old not in kwargs:
                        continue
                    if new in kwargs:
                        raise TypeError(
                            f"{func.__qualname__}() got both {old}= (deprecated) and {new}="
                        )
                    warnings.warn(
                        f"{func.__qualname__}({old}=...) is deprecated, use {new}=... (ADR 0001)",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                    kwargs[new] = kwargs.pop(old)
            return func(*args, **kwargs)

        vars(wrapper)["__renamed_parameters__"] = dict(renames)
        return wrapper

    return decorate
