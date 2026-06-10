import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult
from engine.card_io import CardIO

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"


class TC_INIT_01(BaseTestCase):
    tc_id = "TC-INIT-01"
    title = "Verify applet enable flag activates menu"
    domain = "Applet Init"
    priority = "P1"
    description = "Reads EF_Config (4F01) bytes 0-2 and verifies: byte 0 = 01 (applet enabled), byte 1 = 01 (auto mode on), byte 2 = active IMSI index in range 1-10."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.select_by_path(DF_MULTI)
            self.assert_sw(resp, 0x9000, "Select DF Multi-IMSI")

            resp = self.card.select_by_id(EF_CONFIG)
            self.assert_sw(resp, 0x9000, "Select EF_Config (4F01)")

            resp = self.card.read_binary(0, 3)
            self.assert_sw(resp, 0x9000, "Read EF_Config bytes 0-2")

            self.assert_byte(resp.data, 0, 0x01, "Applet mode byte = 01")
            self.assert_byte(resp.data, 1, 0x01, "Auto mode byte = 01")

            active = resp.data[2]
            ok = 1 <= active <= 10
            status = TestStatus.PASS if ok else TestStatus.FAIL
            self._steps.append(StepResult(
                "Active IMSI index in range 1-10",
                "", resp.data.hex().upper(), status,
                "" if ok else f"Index {active} out of range 1-10"
            ))
            if not ok:
                raise AssertionError(f"Active index {active} invalid")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_INIT_02(BaseTestCase):
    tc_id = "TC-INIT-02"
    title = "Applet disabled — menu must not appear"
    domain = "Applet Init"
    priority = "P1"
    description = "Writes 00 to EF_Config (4F01) byte 0 to disable the applet, reads it back to confirm byte 0 = 00, then restores the original value."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.select_by_path(DF_MULTI)
            self.assert_sw(resp, 0x9000, "Select DF Multi-IMSI")

            resp = self.card.select_by_id(EF_CONFIG)
            self.assert_sw(resp, 0x9000, "Select EF_Config")

            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config (50 bytes)")
            original = bytearray(resp.data)

            disabled = bytearray(original)
            disabled[0] = 0x00
            resp = self.card.update_binary(0, bytes(disabled))
            self.assert_sw(resp, 0x9000, "Write applet mode = 00 (disable)")

            resp = self.card.read_binary(0, 1)
            self.assert_sw(resp, 0x9000, "Read back byte 0")
            self.assert_byte(resp.data, 0, 0x00, "Applet mode byte = 00 (disabled)")

            restored = bytearray(original)
            resp = self.card.update_binary(0, bytes(restored))
            self.assert_sw(resp, 0x9000, "Restore original EF_Config")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_INIT_03(BaseTestCase):
    tc_id = "TC-INIT-03"
    title = "Verify poll interval registration"
    domain = "Applet Init"
    priority = "P2"
    description = "Reads EF_Config (4F01) to determine menu text length X from byte 8, then checks the poll interval byte at offset 9+X and asserts it equals 0x1E (30 seconds)."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.select_by_path(DF_MULTI)
            self.assert_sw(resp, 0x9000, "Select DF Multi-IMSI")

            resp = self.card.select_by_id(EF_CONFIG)
            self.assert_sw(resp, 0x9000, "Select EF_Config")

            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config")
            data = resp.data

            x = data[8]  # Main Menu Text Length at byte 9 (index 8)
            poll_offset = 9 + x
            if poll_offset >= len(data):
                raise AssertionError(
                    f"Poll interval offset {poll_offset} out of range (X={x})"
                )

            self.assert_byte(data, poll_offset, 0x1E,
                             f"Poll interval byte (offset {poll_offset}) = 1E (30s)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_INIT_04(BaseTestCase):
    tc_id = "TC-INIT-04"
    title = "Max IMSI profiles field = 0x0A"
    domain = "Applet Init"
    priority = "P2"
    description = "Reads EF_Config (4F01) bytes 0-5 and asserts byte 5 (max profiles field) equals 0x0A, confirming the card supports up to 10 IMSI profiles."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(0, 6)
            self.assert_sw(resp, 0x9000, "Read EF_Config bytes 0-5")
            self.assert_byte(resp.data, 5, 0x0A, "Max profiles byte (offset 5) = 0x0A")
        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_INIT_05(BaseTestCase):
    tc_id = "TC-INIT-05"
    title = "EF_Config — ISIM / USIM AID fields valid"
    domain = "Applet Init"
    priority = "P1"
    description = "Reads EF_Config (4F01) and locates the ISIM AID length at offset X+21 (10-16 bytes), then validates the USIM AID follows immediately with length 10-16 bytes and a prefix starting A000000087."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.select_by_path(DF_MULTI)
            self.assert_sw(resp, 0x9000, "Select DF Multi-IMSI")

            resp = self.card.select_by_id(EF_CONFIG)
            self.assert_sw(resp, 0x9000, "Select EF_Config")

            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config (50 bytes)")
            data = resp.data

            x = data[8]
            isim_aid_len_offset = 9 + x + 13  # X+22 (0-indexed offset X+21)
            # Per SDS section 3.1.3, byte (X+22) = ADF ISIM AID length
            # Using 0-based: offset = x + 9 + 12 = x+21? Let's use x+21 (0-based)
            isim_len_off = x + 21
            if isim_len_off >= len(data):
                raise AssertionError(f"ISIM AID length offset {isim_len_off} out of range")

            isim_aid_len = data[isim_len_off]
            ok_isim = 0x0A <= isim_aid_len <= 0x10
            status = TestStatus.PASS if ok_isim else TestStatus.FAIL
            self._steps.append(StepResult(
                "ISIM AID length in range 10-16 bytes",
                "", data.hex().upper(), status,
                "" if ok_isim else f"ISIM AID length {isim_aid_len} not in 0x0A-0x10"
            ))
            if not ok_isim:
                raise AssertionError(f"ISIM AID length {isim_aid_len:#04x} invalid")

            usim_len_off = isim_len_off + 1 + isim_aid_len
            if usim_len_off >= len(data):
                raise AssertionError(f"USIM AID length offset {usim_len_off} out of range")

            usim_aid_len = data[usim_len_off]
            ok_usim = 0x0A <= usim_aid_len <= 0x10
            status = TestStatus.PASS if ok_usim else TestStatus.FAIL
            self._steps.append(StepResult(
                "USIM AID length in range 10-16 bytes",
                "", data.hex().upper(), status,
                "" if ok_usim else f"USIM AID length {usim_aid_len} not in 0x0A-0x10"
            ))
            if not ok_usim:
                raise AssertionError(f"USIM AID length {usim_aid_len:#04x} invalid")

            usim_aid_start = usim_len_off + 1
            usim_aid_end = usim_aid_start + usim_aid_len
            if usim_aid_end > len(data):
                raise AssertionError("USIM AID bytes extend beyond EF_Config")

            usim_aid = data[usim_aid_start:usim_aid_end]
            ok_prefix = usim_aid[:5].hex().upper().startswith("A000000087")
            status = TestStatus.PASS if ok_prefix else TestStatus.FAIL
            self._steps.append(StepResult(
                "USIM AID starts with A0000000871",
                "", usim_aid.hex().upper(), status,
                "" if ok_prefix else f"USIM AID prefix {usim_aid[:5].hex().upper()} invalid"
            ))
            if not ok_prefix:
                raise AssertionError("USIM AID does not start with A000000087")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
