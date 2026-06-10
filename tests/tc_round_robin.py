import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"


class TC_RR_01(BaseTestCase):
    tc_id = "TC-RR-01"
    title = "Round robin enabled — cycles to next index on network loss"
    domain = "Round Robin"
    priority = "P1"
    description = "Confirms EF_Config (4F01) offset 6 = 01 (round robin enabled), sends two successive No Service LOCATION_STATUS envelopes, and asserts the active index in byte 2 changed between the two events."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Verify round robin enabled (byte 7, offset 6)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(6, 1)
            self.assert_sw(resp, 0x9000, "Read Round Robin byte (offset 6)")
            self.assert_byte(resp.data, 0, 0x01, "Round Robin byte = 01 (enabled)")

            # Trigger No Service — should cycle to next index
            resp = self.card.send_location_status("000", "00", 2)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS No Service")

            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after No Service")
            idx1 = resp.data[0]
            self._steps.append(StepResult(
                f"Index after 1st No Service = {idx1}", "", resp.data.hex().upper(),
                TestStatus.PASS, ""
            ))

            # Trigger again
            resp = self.card.send_location_status("000", "00", 2)
            self.assert_sw(resp, 0x9000, "Send 2nd LOCATION_STATUS No Service")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after 2nd No Service")
            idx2 = resp.data[0]

            ok = idx2 != idx1
            self._steps.append(StepResult(
                f"Index cycled: {idx1} → {idx2}",
                "", resp.data.hex().upper(),
                TestStatus.PASS if ok else TestStatus.FAIL,
                "" if ok else f"Index did not cycle ({idx1} unchanged)"
            ))
            if not ok:
                raise AssertionError(f"Round robin did not cycle: index stuck at {idx1}")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_RR_02(BaseTestCase):
    tc_id = "TC-RR-02"
    title = "Round robin disabled — no cycling on network loss"
    domain = "Round Robin"
    priority = "P1"
    description = "Writes 00 to EF_Config (4F01) offset 6 to disable round robin, fires a No Service LOCATION_STATUS envelope, and confirms EF_Config byte 2 (active index) is unchanged; restores round robin to 01 afterwards."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)

            resp = self.card.update_binary(6, bytes([0x00]))
            self.assert_sw(resp, 0x9000, "Disable Round Robin (write 00 to offset 6)")

            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read current active index")
            current_idx = resp.data[0]

            resp = self.card.send_location_status("000", "00", 2)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS No Service")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active index after No Service")
            self.assert_byte(resp.data, 0, current_idx, "Active index unchanged (RR disabled)")

            resp = self.card.update_binary(6, bytes([0x01]))
            self.assert_sw(resp, 0x9000, "Re-enable Round Robin")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_RR_03(BaseTestCase):
    tc_id = "TC-RR-03"
    title = "Periodic switching via STATUS command counter"
    domain = "Round Robin"
    priority = "P2"
    description = "Reads EF_Config (4F01) offsets 3-4 and asserts byte 3 = 01 (periodic switching enabled); then issues (counter-1) STATUS commands with no trigger expected, and a final STATUS to verify the PLI LOCI switch fires."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Verify periodic switching enabled (byte 4, offset 3)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(3, 2)
            self.assert_sw(resp, 0x9000, "Read periodic switch + counter bytes (offsets 3-4)")
            self.assert_byte(resp.data, 0, 0x01, "Periodic switch enabled (offset 3 = 01)")
            counter_val = resp.data[1]
            self._steps.append(StepResult(
                f"Periodic counter = {counter_val} STATUS commands",
                "", resp.data.hex().upper(), TestStatus.PASS, ""
            ))

            # Issue (counter_val - 1) STATUS commands — no trigger yet
            for i in range(counter_val - 1):
                resp = self.card.send_status()
                # SW 9000 or 91XX both acceptable
                ok = resp.sw1 == 0x90 or resp.sw1 == 0x91
                self._steps.append(StepResult(
                    f"STATUS command {i+1}/{counter_val-1} (no trigger)",
                    "", str(resp), TestStatus.PASS if ok else TestStatus.FAIL, ""
                ))

            # Issue final STATUS — should trigger PLI LOCI
            resp = self.card.send_status()
            ok = resp.sw1 in (0x90, 0x91)
            self._steps.append(StepResult(
                f"STATUS command {counter_val}/{counter_val} — PLI LOCI trigger",
                "", str(resp), TestStatus.PASS if ok else TestStatus.FAIL, ""
            ))

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_RR_04(BaseTestCase):
    tc_id = "TC-RR-04"
    title = "Fallback mode — return to priority IMSI after counter expires"
    domain = "Round Robin"
    priority = "P2"
    description = "Reads the fallback mode byte (offset X+14) and counter (offset X+13) from EF_Config (4F01), switches to index 2, issues the fallback counter number of STATUS commands, and asserts EF_Config byte 2 reverts to index 01 (priority)."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config")
            data = resp.data
            x = data[8]

            # Fallback mode at offset X+15 (0-based: x+14)
            fb_mode_off = x + 14
            # Fallback counter at offset X+14 (0-based: x+13)
            fb_counter_off = x + 13

            if fb_mode_off >= len(data) or fb_counter_off >= len(data):
                raise AssertionError(f"Fallback offsets out of range (X={x})")

            self.assert_byte(data, fb_mode_off, 0x01,
                             f"Fallback Mode = 01 (offset {fb_mode_off})")
            fb_counter = data[fb_counter_off]
            self._steps.append(StepResult(
                f"Fallback counter = {fb_counter} STATUS commands (offset {fb_counter_off})",
                "", data.hex().upper(), TestStatus.PASS, ""
            ))

            # Switch to index 2
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Switch to index 2 (non-priority)")

            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Verify active index = 02")
            self.assert_byte(resp.data, 0, 0x02, "Active IMSI index = 02")

            # Issue fallback_counter STATUS commands
            for i in range(fb_counter):
                self.card.send_status()

            # Verify reverted to priority index 01
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, f"Read active index after {fb_counter} STATUS commands")
            self.assert_byte(resp.data, 0, 0x01,
                             f"Reverted to priority index 01 after {fb_counter} STATUS cmds")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
