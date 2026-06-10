from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os


class HTMLReporter:
    def __init__(self, results: list, atr: str = ""):
        self._results = results
        self._atr = atr

    def save(self, path: str):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html'])
        )
        template = env.get_template('report.html.j2')

        passed = sum(1 for r in self._results if r.status.value == "PASS")
        failed = sum(1 for r in self._results if r.status.value == "FAIL")
        skipped = sum(1 for r in self._results if r.status.value in ("SKIP", "ERROR"))
        total_ms = sum(r.duration_ms for r in self._results)

        html = template.render(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            atr=self._atr,
            results=self._results,
            stats={
                "pass": passed,
                "fail": failed,
                "skip": skipped,
                "total": len(self._results),
                "duration_s": f"{total_ms / 1000:.1f}",
            }
        )
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
