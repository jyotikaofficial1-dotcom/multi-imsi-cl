import json
from datetime import datetime


class JSONExporter:
    def __init__(self, results: list, atr: str = ""):
        self._results = results
        self._atr = atr

    def save(self, path: str):
        passed = sum(1 for r in self._results if r.status.value == "PASS")
        failed = sum(1 for r in self._results if r.status.value == "FAIL")
        payload = {
            "generated": datetime.now().isoformat(),
            "atr": self._atr,
            "summary": {
                "total": len(self._results),
                "passed": passed,
                "failed": failed,
            },
            "results": [r.serialise_to_dict() for r in self._results],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
