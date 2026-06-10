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
