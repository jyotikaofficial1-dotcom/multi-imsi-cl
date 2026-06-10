import importlib
import pkgutil
import warnings

_registry: dict[str, type] = {}


def discover(package: str = "tests") -> None:
    """Auto-discover all BaseTestCase subclasses in the given package."""
    global _registry
    import tests
    from tests.base_test import BaseTestCase
    for _, modname, _ in pkgutil.walk_packages(tests.__path__, prefix="tests."):
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:
            warnings.warn(f"Could not import {modname}: {exc}", stacklevel=2)
            continue
        for name in dir(mod):
            obj = getattr(mod, name)
            if (isinstance(obj, type)
                    and issubclass(obj, BaseTestCase)
                    and obj is not BaseTestCase
                    and getattr(obj, 'tc_id', '')):
                _registry[obj.tc_id] = obj


def all_tests() -> dict[str, type]:
    """Return all registered test classes keyed by tc_id."""
    return dict(_registry)


def by_domain(domain: str) -> dict[str, type]:
    """Return test classes whose domain matches (case-insensitive)."""
    return {k: v for k, v in _registry.items()
            if getattr(v, 'domain', '').lower() == domain.lower()}


def get(tc_id: str) -> type:
    """Return the class for a given tc_id, raising KeyError if not found."""
    if tc_id not in _registry:
        raise KeyError(f"No test registered with id {tc_id!r}")
    return _registry[tc_id]


# ---------------------------------------------------------------------------
# Class-based interface (used by GUI test tree)
# ---------------------------------------------------------------------------

class TestRegistry:
    """Thin wrapper around the module-level registry for GUI use."""

    def __init__(self):
        discover()

    def all_ids(self) -> list[str]:
        return sorted(_registry.keys())

    def get_class(self, tc_id: str) -> type:
        return get(tc_id)

    def all_domains(self) -> list[str]:
        return sorted({getattr(v, 'domain', '') for v in _registry.values()})

    def get_selected(self, ids: list[str] | None) -> list[type]:
        if ids is None:
            return list(_registry.values())
        return [_registry[i] for i in ids if i in _registry]
