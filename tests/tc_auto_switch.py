import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"
EF_IMSI_LIST = "4F07"
USIM_AID = "A0000000871002FF33FF018900000100"


class TC_AUTO_01(BaseTestCase):
    tc_id = "TC-AUTO-01"
    title = "Normal service — PLMN match → switch to priority IMSI"
    domain = "Auto Switch"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read IMSI_1 from list for later verification
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_IMSI_LIST)
            resp = self.card.read_binary(0, 9)
            self.assert_sw(resp, 0x9000, "Read IMSI_1 from EF_IMSI_List")
            imsi1 = resp.data

            # Trigger Normal Service with MCC=404, MNC=20
            resp = self.card.send_location_status("404", "20", 0)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS Normal Service MCC=404 MNC=20")

            # Verify active IMSI index = 01
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index byte")
            self.assert_byte(resp.data, 0, 0x01, "Active IMSI index = 01")

            # Verify EF_IMSI in ADF USIM matches IMSI_1
            self.card.select_by_aid(USIM_AID)
            self.card.select_by_id("6F07")
            resp = self.card.read_binary(0, 9)
            self.assert_sw(resp, 0x9000, "Read EF_IMSI from ADF USIM")
            self.assert_bytes_equal(resp.data, imsi1, "EF_IMSI matches IMSI_1")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_AUTO_02(BaseTestCase):
    tc_id = "TC-AUTO-02"
    title = "Normal service — PLMN already active, no switch"
    domain = "Auto Switch"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read current active IMSI index")
            current_idx = resp.data[0]

            # Trigger same PLMN again
            resp = self.card.send_location_status("404", "20", 0)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS Normal Service (same PLMN)")

            # Verify no change
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after repeat event")
            self.assert_byte(resp.data, 0, current_idx, f"Active index unchanged = {current_idx:02X}")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_AUTO_03(BaseTestCase):
    tc_id = "TC-AUTO-03"
    title = "Limited service — PLI LOCI issued, preferred IMSI selected"
    domain = "Auto Switch"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Trigger Limited Service
            resp = self.card.send_location_status("424", "02", 1)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS Limited Service MCC=424")

            # Verify active IMSI index = 02 (UAE preference)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, 0x02, "Active IMSI index = 02 (UAE preferred)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_AUTO_04(BaseTestCase):
    tc_id = "TC-AUTO-04"
    title = "PLMN not in MCC list — switch to default IMSI index"
    domain = "Auto Switch"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Trigger Normal Service with unknown PLMN (MCC=999 MNC=01)
            resp = self.card.send_location_status("999", "01", 0)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS with unknown PLMN MCC=999")

            # Verify switch to default index 01
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, 0x01, "Active IMSI index = 01 (default/wildcard)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_AUTO_05(BaseTestCase):
    tc_id = "TC-AUTO-05"
    title = "Automatic mode disabled — no IMSI switch on location event"
    domain = "Auto Switch"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)

            # Disable automatic mode (byte 1, offset 1)
            resp = self.card.update_binary(1, bytes([0x00]))
            self.assert_sw(resp, 0x9000, "Disable automatic mode (write 00 to offset 1)")

            # Read current active index
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read current active IMSI index")
            current_idx = resp.data[0]

            # Trigger a location event that would normally switch
            resp = self.card.send_location_status("404", "20", 0)
            self.assert_sw(resp, 0x9000, "Send LOCATION_STATUS (auto mode off)")

            # Verify no switch
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after event")
            self.assert_byte(resp.data, 0, current_idx, "Active index unchanged (auto mode off)")

            # Re-enable automatic mode
            resp = self.card.update_binary(1, bytes([0x01]))
            self.assert_sw(resp, 0x9000, "Re-enable automatic mode")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
