"""Lazy deprecated aliases for renamed public names (ADR 0001, PLAN.md 3.9).

French public names stay importable until 1.0.0 and emit a ``DeprecationWarning``. Each
module that renamed something used to carry its own copy of that logic, with slightly
different messages. This leaf builds the module-level ``__getattr__`` once::

    __getattr__ = lazy_aliases(__name__, {"OldName": Alias(NewName, "archlux.mod.NewName")})

Behaviour, identical to the copies it replaces: the warning is attributed to the caller;
``from module import OldName`` warns once (the import machinery probes with ``hasattr``
first); any other name raises ``AttributeError``. Aliases are not listed in ``__all__``.

An :class:`Alias` needs its ``value`` already imported: fine for a cheap module, wrong
for a package facade (PLAN.md phase 4, block 1) where the point is that importing one
name must not import the others. :class:`LazyAlias` and :func:`lazy_module_attributes`
solve the two halves of that: a deprecated name resolved without importing its module
until asked, and the package's own current names resolved the same way::

    _ATTRS = {"CurrentName": "archlux.pkg.module"}  # name -> the module defining it
    __getattr__ = lazy_aliases(
        __name__,
        {"OldName": LazyAlias("archlux.pkg.module", "CurrentName", "archlux.pkg.CurrentName")},
        fallback=lazy_module_attributes(__name__, globals(), _ATTRS),
    )

A whole module renamed keeps its old path as a shim built by :func:`module_shim`::

    __getattr__ = module_shim(__name__, "archlux.pkg.new_module")

Renamed keyword parameters of a public function go through :func:`renamed_parameters`::

    @renamed_parameters({"chemin": "path"})
    def write(plan: Plan, path: str | Path) -> None: ...

Renamed fields, class constants and methods of a public class go through
:func:`renamed_attributes`, written above ``@dataclass``::

    @renamed_attributes({"chemin": "path"})
    @dataclass(frozen=True)
    class Report:
        path: str

A leaf: it imports nothing from archlux, so every layer may use it.
"""

from __future__ import annotations

import functools
import importlib
import sys
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "Alias",
    "LazyAlias",
    "lazy_aliases",
    "lazy_module_attributes",
    "module_shim",
    "renamed_attributes",
    "renamed_parameters",
]

_P = ParamSpec("_P")
_R = TypeVar("_R")
_C = TypeVar("_C", bound=type)

_SERVED: dict[str, Mapping[str, Alias | LazyAlias]] = {}
"""Deprecated names each module serves through :func:`lazy_aliases`, by module name.

Read by :func:`module_shim`, so that a module kept under its old name forwards the old
names the module itself still serves, without a second copy of that table."""


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


@dataclass(frozen=True, slots=True)
class LazyAlias:
    """A deprecated name resolved on first use, without importing its module eagerly.

    Same warning contract as :class:`Alias`; the difference is what has to be imported
    to answer it. Use this over :class:`Alias` whenever the current name lives in a
    module a caller might not otherwise need (a package facade, PLAN.md phase 4).

    Parameters
    ----------
    module : str
        Dotted path of the module defining the current name.
    attr : str
        Name of the attribute in that module.
    replacement : str
        The new name, as written in the warning ("use ...").
    note : str, optional
        Same as :attr:`Alias.note`.
    """

    module: str
    attr: str
    replacement: str
    note: str = ""


def lazy_aliases(
    module_name: str,
    aliases: Mapping[str, Alias | LazyAlias],
    *,
    fallback: Callable[[str], object] | None = None,
) -> Callable[[str], object]:
    """Build the module ``__getattr__`` that serves ``aliases`` with a warning.

    Parameters
    ----------
    module_name : str
        ``__name__`` of the module, used in the message and in ``AttributeError``.
    aliases : mapping of str to Alias or LazyAlias
        Old name to its :class:`Alias` (value already in hand) or :class:`LazyAlias`
        (value imported on first use).
    fallback : callable, optional
        Serves every other name (the module's own lazy attributes, e.g. built by
        :func:`lazy_module_attributes`). It must raise ``AttributeError`` for a name it
        does not know. Without it, other names raise.

    Returns
    -------
    callable
        A function to assign to ``__getattr__`` at module level.
    """
    _SERVED[module_name] = aliases

    def __getattr__(name: str) -> object:
        alias = aliases.get(name)
        if alias is None:
            if fallback is not None:
                return fallback(name)
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
        if isinstance(alias, LazyAlias):
            value = getattr(importlib.import_module(alias.module), alias.attr)
        else:
            value = alias.value
        if sys._getframe(1).f_code.co_filename.startswith("<frozen importlib"):
            # `from module import name` probes with hasattr first: warn only once.
            return value
        note = f": {alias.note}" if alias.note else ""
        warnings.warn(
            f"{module_name}.{name} is deprecated, use {alias.replacement}{note} (ADR 0001)",
            DeprecationWarning,
            stacklevel=2,
        )
        return value

    return __getattr__


def lazy_module_attributes(
    module_name: str, module_globals: dict[str, object], attrs: Mapping[str, str]
) -> Callable[[str], object]:
    """Build a ``fallback`` that imports a name's module only when the name is used.

    The resolved value is cached in ``module_globals`` (pass the calling module's own
    ``globals()``), so later lookups find it as a plain attribute and never reach
    ``__getattr__`` again.

    Parameters
    ----------
    module_name : str
        ``__name__`` of the module, used in the ``AttributeError`` message.
    module_globals : dict
        The importing module's ``globals()``.
    attrs : mapping of str to str
        Public name to the dotted path of the module that defines it (the name inside
        that module is the same as the key).

    Returns
    -------
    callable
        Raises ``AttributeError`` for a name not in ``attrs``, as the ``fallback``
        parameter of :func:`lazy_aliases` requires.

    Examples
    --------
    >>> fallback = lazy_module_attributes("pkg", {}, {"Alias": "archlux._deprecation"})
    >>> fallback("Alias") is Alias
    True
    >>> fallback("NoSuchName")
    Traceback (most recent call last):
        ...
    AttributeError: module 'pkg' has no attribute 'NoSuchName'
    """

    def _fallback(name: str) -> object:
        module = attrs.get(name)
        if module is None:
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
        value = getattr(importlib.import_module(module), name)
        module_globals[name] = value  # resolved once: later lookups skip __getattr__
        return value

    return _fallback


def module_shim(module_name: str, new_module: str) -> Callable[[str], object]:
    """Build the ``__getattr__`` of a module kept under its old name (ADR 0001).

    The shim serves, with a ``DeprecationWarning`` naming the new path, every name of
    ``new_module.__all__`` and every deprecated name ``new_module`` itself serves through
    :func:`lazy_aliases` (the French names it carried before the rename). Old pickles
    naming a class by its old module path load through it, with the same warning.

    Parameters
    ----------
    module_name : str
        ``__name__`` of the shim (the old module path).
    new_module : str
        Dotted path of the module that now holds the code.

    Returns
    -------
    callable
        A function to assign to ``__getattr__`` at module level.
    """
    target = importlib.import_module(new_module)
    aliases: dict[str, Alias | LazyAlias] = {
        name: LazyAlias(new_module, name, f"{new_module}.{name}")
        for name in getattr(target, "__all__", ())
    }
    aliases.update(_SERVED.get(new_module, {}))
    return lazy_aliases(module_name, aliases)


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


class _DeprecatedAttribute:
    """Class-level descriptor serving an old attribute name, with a warning.

    Reading goes to the new attribute of the instance, or of the class when read on the
    class (a class constant, a method); writing goes to the new attribute too, so that a
    frozen dataclass still refuses it.
    """

    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def _warn(self, owner: type) -> None:
        warnings.warn(
            f"{owner.__qualname__}.{self.old} is deprecated, use {self.new} (ADR 0001)",
            DeprecationWarning,
            stacklevel=3,
        )

    def __get__(self, instance: object | None, owner: type) -> object:
        self._warn(owner)
        return getattr(owner if instance is None else instance, self.new)

    def __set__(self, instance: object, value: object) -> None:
        self._warn(type(instance))
        setattr(instance, self.new, value)


def renamed_attributes(renames: Mapping[str, str]) -> Callable[[_C], _C]:
    """Serve the old names of renamed fields, class constants and methods of a class.

    Parameters
    ----------
    renames : mapping of str to str
        Old attribute name to its new name. Strings, like the keys of
        :func:`lazy_aliases`, so the old names never appear as identifiers.

    Returns
    -------
    callable
        A class decorator, written above ``@dataclass``. Each old name reads (and
        writes) the new attribute with a ``DeprecationWarning``; the old names that are
        parameters of ``__init__`` stay accepted as keywords through
        :func:`renamed_parameters`.

    Examples
    --------
    >>> import warnings
    >>> from dataclasses import dataclass
    >>> @renamed_attributes({"chemin": "path"})
    ... @dataclass(frozen=True)
    ... class Report:
    ...     path: str
    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter("always")
    ...     Report(chemin="a.json").chemin
    'a.json'
    >>> [str(w.message) for w in caught]  # doctest: +NORMALIZE_WHITESPACE
    ['Report.__init__(chemin=...) is deprecated, use path=... (ADR 0001)',
     'Report.chemin is deprecated, use path (ADR 0001)']
    """

    def decorate(cls: _C) -> _C:
        for old, new in renames.items():
            setattr(cls, old, _DeprecatedAttribute(old, new))
        init = vars(cls).get("__init__")
        if init is not None:
            parameters = init.__code__.co_varnames[: init.__code__.co_argcount]
            parameters += init.__code__.co_varnames[
                init.__code__.co_argcount : init.__code__.co_argcount
                + init.__code__.co_kwonlyargcount
            ]
            keywords = {old: new for old, new in renames.items() if new in parameters}
            if keywords:
                cls.__init__ = renamed_parameters(keywords)(init)  # type: ignore[misc]
        return cls

    return decorate
