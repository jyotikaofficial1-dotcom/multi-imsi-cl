"""Test case registry — discovers and stores BaseTest subclasses."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.base_test import BaseTest

_REGISTRY: dict[str, Type["BaseTest"]] = {}


def register(cls: Type["BaseTest"]) -> Type["BaseTest"]:
    """
    Class decorator that registers a BaseTest subclass by its TC_ID.

    Usage::

        @register
        class IMSI001(BaseTest):
            TC_ID = "IMSI-001"
            ...
    """
    if not cls.TC_ID:
        raise ValueError(f"Test class {cls.__name__} must define a non-empty TC_ID")
    if cls.TC_ID in _REGISTRY:
        raise KeyError(f"Duplicate TC_ID '{cls.TC_ID}' — already registered by {_REGISTRY[cls.TC_ID].__name__}")
    _REGISTRY[cls.TC_ID] = cls
    return cls


def get(tc_id: str) -> Type["BaseTest"]:
    """Return the test class for the given TC_ID."""
    try:
        return _REGISTRY[tc_id]
    except KeyError:
        raise KeyError(f"No test registered with TC_ID '{tc_id}'") from None


def all_tests() -> dict[str, Type["BaseTest"]]:
    """Return a shallow copy of the full registry."""
    return dict(_REGISTRY)


def by_domain(domain: str) -> dict[str, Type["BaseTest"]]:
    """Return all tests belonging to a given domain (case-insensitive)."""
    domain_lower = domain.lower()
    return {
        tc_id: cls
        for tc_id, cls in _REGISTRY.items()
        if cls.DOMAIN.lower() == domain_lower
    }


def discover(package: str = "tests") -> None:
    """
    Auto-import all modules inside *package* so that @register decorators fire.

    Args:
        package: Dotted package name to walk, e.g. ``"tests"``.
    """
    pkg = importlib.import_module(package)
    pkg_path = getattr(pkg, "__path__", [])

    for _finder, module_name, _is_pkg in pkgutil.walk_packages(
        path=pkg_path,
        prefix=f"{package}.",
        onerror=lambda name: None,
    ):
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            import warnings
            warnings.warn(f"Could not import {module_name}: {exc}", stacklevel=2)


def summary() -> str:
    """Return a formatted summary of all registered tests."""
    if not _REGISTRY:
        return "No tests registered."
    lines = ["Registered test cases:"]
    for tc_id in sorted(_REGISTRY):
        cls = _REGISTRY[tc_id]
        lines.append(f"  [{cls.DOMAIN:12s}] {tc_id:20s} — {cls.TITLE}")
    return "\n".join(lines)


class TestRegistry:
    """
    Object-oriented façade over the module-level registry functions.

    Used by the GUI (TestTree, MainWindow) and the CLI runner so they can
    work with a single instance rather than importing bare module functions.
    """

    def __init__(self, package: str = "tests"):
        discover(package)

    # ------------------------------------------------------------------
    # Introspection helpers used by the GUI
    # ------------------------------------------------------------------

    @property
    def _classes(self) -> dict:
        """
        Return a dict mapping TC_ID -> class with lower-case attribute aliases
        so the GUI can use ``cls.title`` / ``cls.domain`` as well as the
        canonical ``cls.TITLE`` / ``cls.DOMAIN``.
        """
        result = {}
        for tc_id, cls in _REGISTRY.items():
            # Wrap in a proxy only if the lower-case attrs are missing
            if not hasattr(cls, 'title'):
                cls.title = cls.TITLE  # type: ignore[attr-defined]
            if not hasattr(cls, 'domain'):
                cls.domain = cls.DOMAIN  # type: ignore[attr-defined]
            if not hasattr(cls, 'tc_id'):
                cls.tc_id = cls.TC_ID  # type: ignore[attr-defined]
            result[tc_id] = cls
        return result

    def all_ids(self) -> list[str]:
        """Return a sorted list of all registered TC_IDs."""
        return sorted(_REGISTRY.keys())

    def get_class(self, tc_id: str):
        """Return the test class for *tc_id*, or raise KeyError."""
        return get(tc_id)

    def get_selected(self, tc_ids: list[str]) -> list:
        """Return test classes for the given list of TC_IDs (skip unknown)."""
        classes = []
        for tc_id in tc_ids:
            try:
                classes.append(get(tc_id))
            except KeyError:
                pass
        return classes

    def all_classes(self) -> list:
        """Return all registered test classes sorted by TC_ID."""
        return [_REGISTRY[k] for k in sorted(_REGISTRY.keys())]
