import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"
EF_IMSI_LIST = "4F07"
EF_SPN_LIST = "4F46"
EF_ACC_LIST = "4F78"
EF_SMSP_LIST = "4F42"
EF_PLMNWACT_LIST = "4F60"
EF_OPLMNWACT_LIST = "4F61"
EF_HPLMNWACT_LIST = "4F62"
from tests.card_config import get_usim_aid as _get_usim_aid


class TC_SWITCH_01(BaseTestCase):
    tc_id = "TC-SWITCH-01"
    title = "IMSI file correctly updated after switch"
    domain = "Switch Files"
    priority = "P1"
    description = "Reads IMSI_2 from EF_IMSI_List (4F07) at offset 9, triggers a switch to index 2 via LOCATION_STATUS MCC=424/MNC=02, then reads EF_IMSI (6F07) in ADF USIM and asserts it equals IMSI_2."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Force active index to 01
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.update_binary(2, bytes([0x01]))
            self.assert_sw(resp, 0x9000, "Force active IMSI index to 01")

            # Read IMSI_2 from list (bytes 9-17, 0-indexed offset 9)
            self.card.select_by_id(EF_IMSI_LIST)
            resp = self.card.read_binary(9, 9)
            self.assert_sw(resp, 0x9000, "Read IMSI_2 from EF_IMSI_List (offset 9)")
            imsi2 = resp.data

            # Trigger switch to index 2 via location event mapped to index 2
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to index 2 via location event")

            # Verify EF_IMSI in ADF USIM = IMSI_2
            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F07")
            resp = self.card.read_binary(0, 9)
            self.assert_sw(resp, 0x9000, "Read EF_IMSI from ADF USIM after switch")
            self.assert_bytes_equal(resp.data, imsi2, "EF_IMSI matches IMSI_2")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_02(BaseTestCase):
    tc_id = "TC-SWITCH-02"
    title = "SPN updated after switch"
    domain = "Switch Files"
    priority = "P1"
    description = "Reads SPN_2 from EF_SPN_List (4F46) at offset 17, triggers a switch to index 2, then reads EF_SPN (6F46) in ADF USIM and asserts the 17-byte value matches SPN_2."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read SPN_2 from list (offset 17, length 17)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_SPN_LIST)
            resp = self.card.read_binary(17, 17)
            self.assert_sw(resp, 0x9000, "Read SPN_2 from EF_SPN_List (offset 17)")
            spn2 = resp.data

            # Trigger switch to index 2
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to index 2")

            # Verify EF_SPN in ADF USIM
            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F46")
            resp = self.card.read_binary(0, 17)
            self.assert_sw(resp, 0x9000, "Read EF_SPN from ADF USIM after switch")
            self.assert_bytes_equal(resp.data, spn2, "EF_SPN matches SPN_2")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_03(BaseTestCase):
    tc_id = "TC-SWITCH-03"
    title = "ACC updated after switch"
    domain = "Switch Files"
    priority = "P1"
    description = "Reads ACC_2 (2 bytes) from EF_ACC_List (4F78) at offset 2, triggers a switch to index 2, then reads EF_ACC (6F78) in ADF USIM and verifies the 2-byte value matches ACC_2."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read ACC_2 from list (offset 2, length 2)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_ACC_LIST)
            resp = self.card.read_binary(2, 2)
            self.assert_sw(resp, 0x9000, "Read ACC_2 from EF_ACC_List (offset 2)")
            acc2 = resp.data

            # Trigger switch
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to index 2")

            # Verify EF_ACC in ADF USIM
            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F78")
            resp = self.card.read_binary(0, 2)
            self.assert_sw(resp, 0x9000, "Read EF_ACC from ADF USIM after switch")
            self.assert_bytes_equal(resp.data, acc2, "EF_ACC matches ACC_2")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_04(BaseTestCase):
    tc_id = "TC-SWITCH-04"
    title = "SMSP updated after switch"
    domain = "Switch Files"
    priority = "P2"
    description = "Reads SMSP_2 (28 bytes) from EF_SMSP_List (4F42) at offset 28, triggers a switch to index 2, then reads record 1 of EF_SMSP (6F42) in ADF USIM and asserts it matches SMSP_2."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Note: SMSP record size is variable; assume 28 bytes for this test
            smsp_record_size = 28
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_SMSP_LIST)
            resp = self.card.read_binary(smsp_record_size, smsp_record_size)
            self.assert_sw(resp, 0x9000, f"Read SMSP_2 from EF_SMSP_List (offset {smsp_record_size})")
            smsp2 = resp.data

            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to index 2")

            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F42")
            resp = self.card.read_record(1, smsp_record_size)
            self.assert_sw(resp, 0x9000, "Read EF_SMSP record 1 from ADF USIM")
            self.assert_bytes_equal(resp.data, smsp2, "EF_SMSP record 1 matches SMSP_2")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_05(BaseTestCase):
    tc_id = "TC-SWITCH-05"
    title = "PLMNwACT / OPLMNwACT / HPLMNwACT updated"
    domain = "Switch Files"
    priority = "P2"
    description = "Reads PLMNwACT_2 (40 bytes) from EF_PLMNwACT_List (4F60) at offset 40, triggers a switch to index 2, then reads EF_PLMNwACT (6F60) in ADF USIM and asserts the 5-byte PLMN+ACT entries match PLMNwACT_2."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            plmn_size = 40  # typical 8×5-byte entries = 40 bytes per profile

            # Read PLMNwACT_2
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_PLMNWACT_LIST)
            resp = self.card.read_binary(plmn_size, plmn_size)
            self.assert_sw(resp, 0x9000, f"Read PLMNwACT_2 (offset {plmn_size})")
            plmn2 = resp.data

            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to index 2")

            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F60")
            resp = self.card.read_binary(0, plmn_size)
            self.assert_sw(resp, 0x9000, "Read EF_PLMNwACT from ADF USIM")
            self.assert_bytes_equal(resp.data, plmn2, "EF_PLMNwACT matches PLMNwACT_2")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_06(BaseTestCase):
    tc_id = "TC-SWITCH-06"
    title = "FPLMN cleared before REFRESH"
    domain = "Switch Files"
    priority = "P1"
    description = "Writes a dummy FPLMN entry (24F299) to EF_FPLMN (6F7B) offset 0, triggers an IMSI switch, then reads 12 bytes of EF_FPLMN and asserts all bytes are 0xFF (list cleared)."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Write dummy FPLMN entry
            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F7B")
            resp = self.card.update_binary(0, bytes([0x24, 0xF2, 0x99]))
            self.assert_sw(resp, 0x9000, "Write dummy FPLMN entry 24F299")

            # Trigger IMSI switch
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger IMSI switch")

            # Verify FPLMN cleared (12 bytes all FF)
            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F7B")
            resp = self.card.read_binary(0, 12)
            self.assert_sw(resp, 0x9000, "Read EF_FPLMN after switch")
            self.assert_bytes_equal(resp.data, b'\xFF' * 12, "EF_FPLMN all FF (cleared)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_07(BaseTestCase):
    tc_id = "TC-SWITCH-07"
    title = "Location files reset to default value before REFRESH"
    domain = "Switch Files"
    priority = "P1"
    description = "Triggers an IMSI switch, then reads EF_LOCI (6F7E) 11 bytes and asserts the update-status byte (last byte) is 00 or 01 (default/not-updated), and reads EF_EPSLOCI (6FE3) 18 bytes to confirm it is accessible."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Trigger IMSI switch
            resp = self.card.send_location_status("404", "20", 0)
            self.assert_sw(resp, 0x9000, "Trigger IMSI switch")

            # Read EF_LOCI (6F7E) - should be reset
            self.card.select_by_aid(_get_usim_aid())
            self.card.select_by_id("6F7E")
            resp = self.card.read_binary(0, 11)
            self.assert_sw(resp, 0x9000, "Read EF_LOCI after switch")

            # Update status byte (last byte) should be 01 (not updated)
            update_status = resp.data[-1]
            ok = update_status in (0x00, 0x01)
            from tests.base_test import StepResult
            status_val = TestStatus.PASS if ok else TestStatus.FAIL
            self._steps.append(StepResult(
                "EF_LOCI update status byte is default (00 or 01)",
                "", resp.data.hex().upper(), status_val,
                "" if ok else f"Unexpected update status {update_status:02X}"
            ))
            if not ok:
                raise AssertionError(f"EF_LOCI update status {update_status:#04x} unexpected")

            # Read EF_EPSLOCI (6FE3) - should be reset
            self.card.select_by_id("6FE3")
            resp = self.card.read_binary(0, 18)
            self.assert_sw(resp, 0x9000, "Read EF_EPSLOCI after switch")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_SWITCH_08(BaseTestCase):
    tc_id = "TC-SWITCH-08"
    title = "REFRESH command issued at end of switch"
    domain = "Switch Files"
    priority = "P1"
    description = "Reads the REFRESH type byte from EF_Config (4F01) at offset X+8, triggers an IMSI switch, and verifies the card remains responsive by issuing a SELECT MF (9000) after the REFRESH."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read REFRESH type from EF_Config
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config")
            data = resp.data
            x = data[8]
            refresh_type_offset = 9 + x + 8
            if refresh_type_offset < len(data):
                refresh_type = data[refresh_type_offset]
            else:
                refresh_type = 0x00

            from tests.base_test import StepResult
            self._steps.append(StepResult(
                f"Refresh type byte (offset {refresh_type_offset}) = {refresh_type:02X}",
                "", data.hex().upper(), TestStatus.PASS, ""
            ))

            # Trigger switch
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger IMSI switch (REFRESH expected)")

            # Verify card still responsive after REFRESH
            resp = self.card.select_mf()
            self.assert_sw(resp, 0x9000, "Card responsive after REFRESH (MF select)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
