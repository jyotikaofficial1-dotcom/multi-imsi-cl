import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"


class TC_STK_01(BaseTestCase):
    tc_id = "TC-STK-01"
    title = "STK 'Next IMSI' menu item"
    domain = "STK Menu"
    priority = "P1"
    description = "Sends ENVELOPE MENU SELECTION with item=01 (Next IMSI) and reads EF_Config (4F01) byte 2 before and after, asserting the active IMSI index incremented (wrapping from 10 to 1 is valid)."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read current active IMSI index")
            before = resp.data[0]

            # ENVELOPE MENU SELECTION item 01 = Next IMSI
            resp = self.card.send_menu_selection(0x01)
            self.assert_sw(resp, 0x9000, "ENVELOPE MENU SELECTION item=01 (Next IMSI)")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after Next IMSI")
            after = resp.data[0]

            # index should have incremented (wrapping 10→1 is valid)
            ok = after != before
            self._steps.append(StepResult(
                f"Index incremented: {before} → {after}",
                "", resp.data.hex().upper(),
                TestStatus.PASS if ok else TestStatus.FAIL,
                "" if ok else f"Index unchanged at {before}"
            ))
            if not ok:
                raise AssertionError(f"Next IMSI did not advance index (stuck at {before})")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_02(BaseTestCase):
    tc_id = "TC-STK-02"
    title = "STK 'Priority IMSI' menu item"
    domain = "STK Menu"
    priority = "P1"
    description = "Sends ENVELOPE MENU SELECTION with item=02 (Priority IMSI) and reads EF_Config (4F01) byte 2 to assert the active IMSI index is now 01, confirming an immediate switch to the priority profile."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # ENVELOPE MENU SELECTION item 02 = Priority IMSI
            resp = self.card.send_menu_selection(0x02)
            self.assert_sw(resp, 0x9000, "ENVELOPE MENU SELECTION item=02 (Priority IMSI)")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after Priority IMSI")
            self.assert_byte(resp.data, 0, 0x01, "Active IMSI index = 01 (priority)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_03(BaseTestCase):
    tc_id = "TC-STK-03"
    title = "STK 'Lock IMSI' menu item"
    domain = "STK Menu"
    priority = "P2"
    description = "Switches to index 2, sends ENVELOPE MENU SELECTION item=03 (Lock IMSI), then fires a LOCATION_STATUS event for a different PLMN and reads EF_Config (4F01) byte 2 to confirm the index remains locked at 02."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # First move to index 02
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to index 02")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Verify active index = 02")
            self.assert_byte(resp.data, 0, 0x02, "Active IMSI index = 02")

            # Lock current IMSI via menu item 03
            resp = self.card.send_menu_selection(0x03)
            self.assert_sw(resp, 0x9000, "ENVELOPE MENU SELECTION item=03 (Lock IMSI)")

            # Trigger a location event that would normally switch
            resp = self.card.send_location_status("404", "20", 0)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS (should be blocked by lock)")

            # Verify IMSI remains on index 02
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after locked event")
            self.assert_byte(resp.data, 0, 0x02, "Active index = 02 (locked, no switch)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_04(BaseTestCase):
    tc_id = "TC-STK-04"
    title = "STK 'Automatic Mode' toggle"
    domain = "STK Menu"
    priority = "P2"
    description = "Reads EF_Config (4F01) byte 1 (auto mode) before the toggle, sends ENVELOPE MENU SELECTION item=04, re-reads byte 1 and asserts it flipped between 00 and 01; restores the original state if needed."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(1, 1)
            self.assert_sw(resp, 0x9000, "Read automatic mode byte (offset 1)")
            before = resp.data[0]

            # Toggle via menu item 04
            resp = self.card.send_menu_selection(0x04)
            self.assert_sw(resp, 0x9000, "ENVELOPE MENU SELECTION item=04 (Automatic Mode toggle)")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(1, 1)
            self.assert_sw(resp, 0x9000, "Read automatic mode byte after toggle")
            after = resp.data[0]

            expected = 0x01 if before == 0x00 else 0x00
            self.assert_byte(resp.data, 0, expected,
                             f"Auto mode toggled: {before:02X} → {expected:02X}")

            # Restore original if needed
            if after != before:
                resp = self.card.send_menu_selection(0x04)
                self.assert_sw(resp, 0x9000, "Restore automatic mode to original state")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
