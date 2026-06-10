"""Test runner — executes registered test cases and collects results."""
from __future__ import annotations

import time
from typing import Callable, Optional, Sequence, TYPE_CHECKING

from engine.card_io import CardIO
from runner.result import TestResult, TestStatus
from runner import registry as reg

if TYPE_CHECKING:
    from tests.base_test import BaseTest

# Callback type: called after each test completes
ProgressCallback = Callable[[TestResult], None]


class TestRunner:
    """
    Orchestrates test discovery, execution and result aggregation.

    Usage::

        runner = TestRunner(card_io)
        runner.discover()                          # auto-import tests package
        results = runner.run_all()                 # run everything
        results = runner.run_domain("IMSI")        # run one domain
        results = runner.run_ids(["IMSI-001"])     # run specific IDs
    """

    def __init__(
        self,
        card: CardIO,
        progress_cb: Optional[ProgressCallback] = None,
    ):
        self._card = card
        self._progress_cb = progress_cb
        self._results: list[TestResult] = []

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, package: str = "tests") -> None:
        """Import all test modules so @register decorators are executed."""
        reg.discover(package)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_all(self) -> list[TestResult]:
        """Run every registered test case in TC_ID alphabetical order."""
        tc_ids = sorted(reg.all_tests().keys())
        return self._run_ids(tc_ids)

    def run_domain(self, domain: str) -> list[TestResult]:
        """Run all test cases belonging to *domain*."""
        tc_ids = sorted(reg.by_domain(domain).keys())
        return self._run_ids(tc_ids)

    def run_ids(self, tc_ids: Sequence[str]) -> list[TestResult]:
        """Run a specific list of test cases by TC_ID."""
        return self._run_ids(list(tc_ids))

    def run_single(self, tc_id: str) -> TestResult:
        """Run a single test case and return its result."""
        results = self._run_ids([tc_id])
        return results[0]

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    @property
    def results(self) -> list[TestResult]:
        """All results collected since construction (or last reset)."""
        return list(self._results)

    def reset(self) -> None:
        """Clear accumulated results."""
        self._results.clear()

    def summary(self) -> dict[str, int]:
        """
        Return a count of each TestStatus across all collected results.

        Example::

            {"PASS": 5, "FAIL": 1, "SKIP": 0, "ERROR": 0}
        """
        counts: dict[str, int] = {s.value: 0 for s in TestStatus}
        for r in self._results:
            counts[r.status.value] += 1
        return counts

    def passed(self) -> bool:
        """Return True iff there are no FAIL or ERROR results."""
        return all(
            r.status in (TestStatus.PASS, TestStatus.SKIP)
            for r in self._results
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_ids(self, tc_ids: list[str]) -> list[TestResult]:
        batch: list[TestResult] = []
        for tc_id in tc_ids:
            result = self._run_one(tc_id)
            batch.append(result)
            self._results.append(result)
            if self._progress_cb:
                try:
                    self._progress_cb(result)
                except Exception:  # noqa: BLE001
                    pass
        return batch

    def _run_one(self, tc_id: str) -> TestResult:
        try:
            cls = reg.get(tc_id)
        except KeyError as exc:
            return TestResult(
                tc_id=tc_id,
                title="<unknown>",
                domain="<unknown>",
                status=TestStatus.ERROR,
                steps=[],
                duration_ms=0.0,
            )

        instance: "BaseTest" = cls(self._card)
        try:
            result = instance.execute()
        except Exception as exc:  # noqa: BLE001
            from runner.result import StepResult
            result = TestResult(
                tc_id=tc_id,
                title=cls.TITLE,
                domain=cls.DOMAIN,
                status=TestStatus.ERROR,
                steps=[
                    StepResult(
                        step="RUNNER_ERROR",
                        apdu_sent="",
                        response="",
                        status=TestStatus.ERROR,
                        message=str(exc),
                    )
                ],
                duration_ms=0.0,
            )
        return result

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def print_summary(self) -> None:
        """Print a concise ASCII summary table to stdout."""
        counts = self.summary()
        total = sum(counts.values())
        print("\n" + "=" * 60)
        print(f"  Test run complete — {total} test(s)")
        print("=" * 60)
        for status, count in counts.items():
            print(f"  {status:<8}: {count}")
        print("=" * 60)
        for result in self._results:
            icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "−", "ERROR": "!"}.get(
                result.status.value, "?"
            )
            print(
                f"  {icon} [{result.domain:12s}] {result.tc_id:20s} "
                f"{result.status.value:5s}  {result.duration_ms:.1f} ms"
            )
        print()

    def serialise_results(self) -> list[dict]:
        """Return all results as a list of plain dicts (JSON-serialisable)."""
        return [r.serialise_to_dict() for r in self._results]
