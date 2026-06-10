import importlib
import pkgutil
import warnings


class TestRegistry:
    """Auto-discovers all BaseTestCase subclasses in the tests/ package."""

    def __init__(self):
        self._classes: dict[str, type] = {}
        self._discover()

    def _discover(self):
        import tests
        from tests.base_test import BaseTestCase
        for _, modname, _ in pkgutil.walk_packages(
                tests.__path__, prefix="tests."):
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
                    self._classes[obj.tc_id] = obj

    def all_ids(self) -> list[str]:
        return sorted(self._classes.keys())

    def get_selected(self, ids: list[str] | None) -> list[type]:
        if ids is None:
            return list(self._classes.values())
        return [self._classes[i] for i in ids if i in self._classes]
