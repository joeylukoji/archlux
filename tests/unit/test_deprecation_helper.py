"""One helper builds the lazy deprecated aliases of a module (PLAN.md 3.9, wave 0).

Four modules used to carry their own copy of this logic, each with a slightly different
message. The helper keeps their observable behaviour: the message, one warning per
``from module import name``, the caller as the warning location, and ``AttributeError``
for anything else.
"""

from __future__ import annotations

import warnings

import pytest

from archlux._deprecation import Alias, LazyAlias, lazy_aliases, lazy_module_attributes

NEW = object()


def module_getattr() -> object:
    return lazy_aliases(
        "archlux.demo",
        {
            "OldName": Alias(NEW, "archlux.demo.NewName"),
            "Noted": Alias(NEW, "NewName", note="a frozen oracle, not a simulation"),
        },
    )


def test_an_alias_returns_the_new_object_and_warns() -> None:
    getattr_ = module_getattr()
    with pytest.warns(DeprecationWarning) as record:
        value = getattr_("OldName")  # type: ignore[operator]
    assert value is NEW
    assert str(record[0].message) == (
        "archlux.demo.OldName is deprecated, use archlux.demo.NewName (ADR 0001)"
    )


def test_a_note_explains_the_rename() -> None:
    getattr_ = module_getattr()
    with pytest.warns(DeprecationWarning) as record:
        getattr_("Noted")  # type: ignore[operator]
    assert str(record[0].message) == (
        "archlux.demo.Noted is deprecated, use NewName: "
        "a frozen oracle, not a simulation (ADR 0001)"
    )


def test_the_warning_points_at_the_caller() -> None:
    getattr_ = module_getattr()
    with pytest.warns(DeprecationWarning) as record:
        getattr_("OldName")  # type: ignore[operator]
    assert record[0].filename == __file__


def test_an_unknown_name_raises_attribute_error() -> None:
    getattr_ = module_getattr()
    with pytest.raises(AttributeError, match=r"archlux.demo"):
        getattr_("Nothing")  # type: ignore[operator]


def test_a_from_import_warns_exactly_once() -> None:
    """``from m import x`` probes with ``hasattr`` first; only the real access warns."""
    import sys
    import types

    module = types.ModuleType("archlux_demo_from_import")
    module.__getattr__ = lazy_aliases(  # type: ignore[attr-defined]
        "archlux_demo_from_import", {"Old": Alias(NEW, "New")}
    )
    sys.modules["archlux_demo_from_import"] = module
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            exec("from archlux_demo_from_import import Old", {})
        assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1
    finally:
        del sys.modules["archlux_demo_from_import"]


def test_a_lazy_alias_imports_only_on_first_use() -> None:
    """PLAN.md phase 4, block 1: a package facade must not import a name's module just
    to build its deprecated-alias table."""
    getattr_ = lazy_aliases(
        "archlux.demo",
        {"OldName": LazyAlias("archlux._deprecation", "Alias", "archlux.demo.Alias")},
    )
    with pytest.warns(DeprecationWarning) as record:
        value = getattr_("OldName")  # type: ignore[operator]
    assert value is Alias
    assert str(record[0].message) == (
        "archlux.demo.OldName is deprecated, use archlux.demo.Alias (ADR 0001)"
    )


def test_lazy_module_attributes_resolves_and_caches() -> None:
    served: dict[str, object] = {}
    fallback = lazy_module_attributes("pkg", served, {"Alias": "archlux._deprecation"})
    assert fallback("Alias") is Alias
    assert served == {"Alias": Alias}  # cached: a later lookup skips __getattr__


def test_lazy_module_attributes_raises_for_an_unknown_name() -> None:
    fallback = lazy_module_attributes("pkg", {}, {"Alias": "archlux._deprecation"})
    with pytest.raises(AttributeError, match="module 'pkg' has no attribute 'Nothing'"):
        fallback("Nothing")


def test_a_fallback_serves_the_names_that_are_not_aliases() -> None:
    """A module with its own lazy attributes keeps them, and still warns only once."""
    import sys
    import types

    served = object()

    def fallback(name: str) -> object:
        if name == "lazy":
            return served
        raise AttributeError(name)

    module = types.ModuleType("archlux_demo_fallback")
    module.__getattr__ = lazy_aliases(  # type: ignore[attr-defined]
        "archlux_demo_fallback", {"Old": Alias(NEW, "New")}, fallback=fallback
    )
    sys.modules["archlux_demo_fallback"] = module
    try:
        assert module.lazy is served  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            module.absent  # type: ignore[attr-defined]  # noqa: B018
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            exec("from archlux_demo_fallback import Old", {})
        assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1
    finally:
        del sys.modules["archlux_demo_fallback"]


@pytest.mark.parametrize("package", ["archlux.light", "archlux.certify"])
def test_a_lazy_facade_raises_the_standard_message_for_an_unknown_name(package: str) -> None:
    import importlib

    with pytest.raises(AttributeError, match=f"^module '{package}' has no attribute 'X'$"):
        importlib.import_module(package).X
