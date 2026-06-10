"""Base class for all Multi-IMSI test cases."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from engine.card_io import CardIO
from engine.apdu import APDUResponse
from engine.sw_table import describe
from runner.result import TestResult, StepResult, TestStatus


class BaseTest(ABC):
    """
    Abstract base for every test case.

    Subclasses must implement:
        - TC_ID   : str  – unique test-case identifier, e.g. "IMSI-001"
        - TITLE   : str  – human-readable description
        - DOMAIN  : str  – category, e.g. "IMSI", "STK", "Security"
        - run()          – the actual test body
    """

    TC_ID: str = ""
    TITLE: str = ""
    DOMAIN: str = ""

    def __init__(self, card: CardIO):
        self._card = card
        self._result: TestResult = TestResult(
            tc_id=self.TC_ID,
            title=self.TITLE,
            domain=self.DOMAIN,
        )
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self) -> TestResult:
        """Entry point called by the test runner."""
        self._result.status = TestStatus.PASS
        self._start_time = time.monotonic()
        try:
            self.run()
        except AssertionError as exc:
            self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
        finally:
            elapsed = time.monotonic() - self._start_time
            self._result.duration_ms = round(elapsed * 1000, 2)
        return self._result

    @abstractmethod
    def run(self) -> None:
        """Subclasses implement the test logic here."""

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def step(
        self,
        name: str,
        apdu_sent: str,
        resp: APDUResponse,
        expect_ok: bool = True,
        expected_sw: Optional[int] = None,
    ) -> StepResult:
        """
        Record a single APDU exchange as a named step.

        Args:
            name:        Human-readable step label.
            apdu_sent:   Hex string of the transmitted APDU.
            resp:        The APDUResponse returned by card.transmit().
            expect_ok:   If True, a non-9000 SW marks the step as FAIL.
            expected_sw: If provided, checks for this exact SW value.

        Returns:
            The created StepResult (already appended to self._result.steps).
        """
        sw_desc = describe(resp.sw_hex)

        if expected_sw is not None:
            ok = resp.sw == expected_sw
            status = TestStatus.PASS if ok else TestStatus.FAIL
            msg = "" if ok else f"Expected SW {expected_sw:04X}, got {resp.sw_hex} ({sw_desc})"
        elif expect_ok:
            status = TestStatus.PASS if resp.ok else TestStatus.FAIL
            msg = "" if resp.ok else f"Unexpected SW {resp.sw_hex}: {sw_desc}"
        else:
            status = TestStatus.PASS
            msg = sw_desc

        sr = StepResult(
            step=name,
            apdu_sent=apdu_sent,
            response=str(resp),
            status=status,
            message=msg,
        )
        self._result.steps.append(sr)

        if status == TestStatus.FAIL:
            self._result.status = TestStatus.FAIL

        return sr

    def assert_sw(self, resp: APDUResponse, expected: int, msg: str = "") -> None:
        """Assert a specific SW code; raises AssertionError on mismatch."""
        if resp.sw != expected:
            detail = f"Expected SW {expected:04X}, got {resp.sw_hex}: {describe(resp.sw_hex)}"
            raise AssertionError(f"{msg} — {detail}" if msg else detail)

    def assert_ok(self, resp: APDUResponse, msg: str = "") -> None:
        """Assert SW == 9000."""
        self.assert_sw(resp, 0x9000, msg)

    def assert_data_contains(self, resp: APDUResponse, expected_hex: str, msg: str = "") -> None:
        """Assert that response data contains the given hex substring."""
        needle = bytes.fromhex(expected_hex)
        if needle not in resp.data:
            detail = (
                f"Expected {expected_hex.upper()} in response data "
                f"{resp.data.hex().upper()}"
            )
            raise AssertionError(f"{msg} — {detail}" if msg else detail)

    def skip(self, reason: str = "") -> None:
        """Mark this test as skipped."""
        self._result.status = TestStatus.SKIP
        if reason:
            self._result.steps.append(
                StepResult(
                    step="SKIP",
                    apdu_sent="",
                    response="",
                    status=TestStatus.SKIP,
                    message=reason,
                )
            )
        raise _SkipException(reason)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fail(self, msg: str) -> None:
        self._result.status = TestStatus.FAIL
        self._result.steps.append(
            StepResult(
                step="ASSERT",
                apdu_sent="",
                response="",
                status=TestStatus.FAIL,
                message=msg,
            )
        )

    def _error(self, msg: str) -> None:
        self._result.status = TestStatus.ERROR
        self._result.steps.append(
            StepResult(
                step="ERROR",
                apdu_sent="",
                response="",
                status=TestStatus.ERROR,
                message=msg,
            )
        )

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def select_mf(self) -> APDUResponse:
        resp = self._card.select_mf()
        self.step("Select MF", "00 A4 00 0C 02 3F 00", resp)
        return resp

    def select_by_path(self, path_hex: str) -> APDUResponse:
        resp = self._card.select_by_path(path_hex)
        self.step(f"Select path {path_hex}", f"00 A4 08 0C .. {path_hex}", resp)
        return resp

    def select_by_aid(self, aid_hex: str) -> APDUResponse:
        resp = self._card.select_by_aid(aid_hex)
        self.step(f"Select AID {aid_hex}", f"00 A4 04 0C .. {aid_hex}", resp)
        return resp


class _SkipException(Exception):
    """Internal exception used to short-circuit skipped tests."""


# ---------------------------------------------------------------------------
# Concrete base used by all generated test cases
# ---------------------------------------------------------------------------

class BaseTestCase(ABC):
    """
    Concrete base expected by every test module in tests/tc_*.py.

    Uses lower-case class attributes (tc_id, title, domain, priority)
    and the run() / _finalise() / assert_* pattern from the architecture spec.
    """

    tc_id: str = ""
    title: str = ""
    domain: str = ""
    priority: str = "P2"

    def __init__(self, card: "CardIO"):
        self.card = card
        self.result = TestResult(self.tc_id, self.title, self.domain)
        self._steps: list[StepResult] = []

    def assert_sw(self, resp: "APDUResponse", expected_sw: int = 0x9000,
                  step_name: str = "") -> None:
        status = TestStatus.PASS if resp.sw == expected_sw else TestStatus.FAIL
        msg = "" if status == TestStatus.PASS else \
              f"Expected {expected_sw:04X}, got {resp.sw_hex}"
        self._steps.append(StepResult(step_name, "", str(resp), status, msg))
        if status == TestStatus.FAIL:
            raise AssertionError(msg)

    def assert_byte(self, data: bytes, offset: int, expected: int,
                    step_name: str = "") -> None:
        actual = data[offset]
        status = TestStatus.PASS if actual == expected else TestStatus.FAIL
        msg = "" if status == TestStatus.PASS else \
              f"Offset {offset}: expected {expected:02X}, got {actual:02X}"
        self._steps.append(StepResult(step_name, "", data.hex().upper(), status, msg))
        if status == TestStatus.FAIL:
            raise AssertionError(msg)

    def assert_bytes_equal(self, actual: bytes, expected: bytes,
                           step_name: str = "") -> None:
        status = TestStatus.PASS if actual == expected else TestStatus.FAIL
        msg = "" if status == TestStatus.PASS else \
              f"Expected {expected.hex().upper()}, got {actual.hex().upper()}"
        self._steps.append(StepResult(step_name, "", actual.hex().upper(), status, msg))
        if status == TestStatus.FAIL:
            raise AssertionError(msg)

    @abstractmethod
    def run(self) -> "TestResult":
        ...

    def _finalise(self, exc: Exception | None = None) -> "TestResult":
        if exc:
            self.result.status = TestStatus.FAIL
        else:
            all_pass = all(s.status == TestStatus.PASS for s in self._steps)
            self.result.status = TestStatus.PASS if all_pass else TestStatus.FAIL
        self.result.steps = self._steps
        return self.result

    # --- convenience wrappers so test cases can call card helpers directly ---

    def send_location_status(self, mcc: str, mnc: str, svc: int):
        return self.card.send_location_status(mcc, mnc, svc)

    def send_menu_selection(self, item_id: int, help_req: bool = False):
        return self.card.send_menu_selection(item_id, help_req)
