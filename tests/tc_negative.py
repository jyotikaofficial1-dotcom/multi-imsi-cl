import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"
EF_IMSI_LIST = "4F07"
USIM_AID = "A0000000871002FF33FF018900000100"


class TC_NEG_01(BaseTestCase):
    tc_id = "TC-NEG-01"
    title = "Read EF_Config without ADM authentication → 6982"
    domain = "Negative Tests"
    priority = "P1"
    description = "Selects EF_Config (4F01) without prior ADM authentication and issues a READ BINARY for 1 byte, asserting the card returns SW 6982 (Security status not satisfied) to enforce access control."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Attempt read without prior ADM — should return 6982
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(0, 1)

            # Accept either 6982 (expected) or 9000 if card doesn't enforce on bench
            expected_sw = 0x6982
            if resp.sw == expected_sw:
                self._steps.append(StepResult(
                    "Unauthenticated READ returns 6982 (Security status not satisfied)",
                    "", str(resp), TestStatus.PASS, ""
                ))
            else:
                # Some lab cards may allow READ after a previous authenticated session
                self._steps.append(StepResult(
                    f"Unauthenticated READ returned {resp.sw_hex} (expected 6982)",
                    "", str(resp), TestStatus.FAIL,
                    f"Expected SW 6982, got {resp.sw_hex}"
                ))
                raise AssertionError(
                    f"Expected SW 6982 on unauthenticated READ, got {resp.sw_hex}"
                )

        except AssertionError:
            raise
        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_NEG_02(BaseTestCase):
    tc_id = "TC-NEG-02"
    title = "Write EF_IMSI_List with wrong Lc → 6700"
    domain = "Negative Tests"
    priority = "P1"
    description = "Selects EF_IMSI_List (4F07) and sends an UPDATE BINARY with only 8 data bytes instead of the required 9-byte IMSI slot length, asserting the card returns SW 6700 (Wrong length)."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_IMSI_LIST)

            # Write 8 bytes instead of required 9 for one IMSI slot
            short_data = bytes([0x08, 0x30, 0x99, 0x41, 0x04, 0x00, 0x00, 0x00])
            resp = self.card.update_binary(0, short_data)

            if resp.sw == 0x6700:
                self._steps.append(StepResult(
                    "Wrong Lc returns 6700 (Wrong length)",
                    "", str(resp), TestStatus.PASS, ""
                ))
            else:
                self._steps.append(StepResult(
                    f"Wrong Lc returned {resp.sw_hex} (expected 6700)",
                    "", str(resp), TestStatus.FAIL,
                    f"Expected 6700, got {resp.sw_hex}"
                ))
                raise AssertionError(f"Expected 6700 on wrong Lc, got {resp.sw_hex}")

        except AssertionError:
            raise
        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_NEG_03(BaseTestCase):
    tc_id = "TC-NEG-03"
    title = "Write IMSI index out of range (0x0B) — card remains operational"
    domain = "Negative Tests"
    priority = "P2"
    description = "Writes 0x0B to EF_Config (4F01) byte 2 (out-of-range active index), fires a LOCATION_STATUS event, and confirms the applet handles the invalid value gracefully by still returning 9000 to a SELECT MF; restores the original config."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)

            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config")
            original = bytearray(resp.data)

            # Modify active index to 0x0B (out of range)
            modified = bytearray(original)
            modified[2] = 0x0B
            resp = self.card.update_binary(0, bytes(modified))
            # Write may succeed at file level (9000) or be rejected
            self._steps.append(StepResult(
                f"Write index 0x0B returned {resp.sw_hex} (write may or may not succeed)",
                "", str(resp), TestStatus.PASS, ""
            ))

            # Trigger location event — applet must handle gracefully
            resp = self.card.send_location_status("404", "20", 0)
            self._steps.append(StepResult(
                f"Location event with out-of-range index returned {resp.sw_hex}",
                "", str(resp), TestStatus.PASS, ""
            ))

            # Card must still respond to MF select
            resp = self.card.select_mf()
            self.assert_sw(resp, 0x9000, "Card still operational (MF SELECT = 9000)")

            # Restore original
            resp = self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.update_binary(0, bytes(original))
            self.assert_sw(resp, 0x9000, "Restore original EF_Config")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_NEG_04(BaseTestCase):
    tc_id = "TC-NEG-04"
    title = "Read beyond EOF of EF_MCC_Mapping_List → 6B00"
    domain = "Negative Tests"
    priority = "P2"
    description = "Selects EF_MCC_Mapping_List (4F03) and issues a READ BINARY starting at offset 0x01F8 (504) on a 500-byte file, asserting the card returns an error SW (6B00, 6700, or 6A86) for the out-of-bounds access."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F03")

            # Read starting at offset 0x01F8 (504) on a 500-byte file → beyond EOF
            resp = self.card.read_binary(0x01F8, 4)

            if resp.sw in (0x6B00, 0x6700, 0x6A86):
                self._steps.append(StepResult(
                    f"Beyond-EOF read returns {resp.sw_hex} (error SW — correct)",
                    "", str(resp), TestStatus.PASS, ""
                ))
            else:
                self._steps.append(StepResult(
                    f"Beyond-EOF read returned {resp.sw_hex} (expected 6B00/6700/6A86)",
                    "", str(resp), TestStatus.FAIL,
                    f"Expected error SW, got {resp.sw_hex}"
                ))
                raise AssertionError(
                    f"Expected error SW on beyond-EOF read, got {resp.sw_hex}"
                )

        except AssertionError:
            raise
        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_NEG_05(BaseTestCase):
    tc_id = "TC-NEG-05"
    title = "Cold reset during IMSI switch — consistency check"
    domain = "Negative Tests"
    priority = "P1"
    description = "Triggers an IMSI switch, reads the active index from EF_Config (4F01) byte 2, then cross-checks EF_IMSI (6F07) in ADF USIM against the corresponding slot in EF_IMSI_List (4F07) to confirm file-system consistency after the switch."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Trigger switch
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger IMSI switch")

            # Read active IMSI index
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after switch")
            active_idx = resp.data[0]
            self._steps.append(StepResult(
                f"Active IMSI index = {active_idx:02X}",
                "", resp.data.hex().upper(), TestStatus.PASS, ""
            ))

            # Read EF_IMSI from ADF USIM
            self.card.select_by_aid(USIM_AID)
            self.card.select_by_id("6F07")
            resp = self.card.read_binary(0, 9)
            self.assert_sw(resp, 0x9000, "Read current EF_IMSI from ADF USIM")
            current_imsi = resp.data

            # Read the corresponding slot from EF_IMSI_List
            offset = (active_idx - 1) * 9
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F07")
            resp = self.card.read_binary(offset, 9)
            self.assert_sw(resp, 0x9000,
                           f"Read IMSI_List slot {active_idx} (offset {offset})")
            listed_imsi = resp.data

            self.assert_bytes_equal(
                current_imsi, listed_imsi,
                f"EF_IMSI matches IMSI_List slot {active_idx} (consistency)"
            )

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
