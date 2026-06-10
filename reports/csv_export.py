import csv
from datetime import datetime


class CSVExporter:
    def __init__(self, results: list):
        self._results = results

    def save(self, path: str):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["tc_id", "domain", "title", "status", "duration_ms"])
            for r in self._results:
                writer.writerow([
                    r.tc_id, r.domain, r.title,
                    r.status.value, f"{r.duration_ms:.1f}"
                ])
