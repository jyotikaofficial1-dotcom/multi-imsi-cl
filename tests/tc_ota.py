import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"
EF_IMSI_LIST = "4F07"
USIM_AID = "A0000000871002FF33FF018900000100"


class TC_OTA_01(BaseTestCase):
    tc_id = "TC-OTA-01"
    title = "Remote update of EF_IMSI_List triggers config reload + REFRESH"
    domain = "OTA"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read current IMSI_3 (offset 18, 9 bytes)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_IMSI_LIST)
            resp = self.card.read_binary(18, 9)
            self.assert_sw(resp, 0x9000, "Read IMSI_3 slot before update (offset 18)")
            original_imsi3 = resp.data

            # Write new value to IMSI slot 3
            new_imsi3 = bytes([0x08, 0x39, 0x94, 0x10, 0x40, 0x00, 0x00, 0x00, 0xF0])
            resp = self.card.update_binary(18, new_imsi3)
            self.assert_sw(resp, 0x9000, "Update IMSI_3 slot via UPDATE BINARY (OTA simulation)")

            # Verify write
            resp = self.card.read_binary(18, 9)
            self.assert_sw(resp, 0x9000, "Read back IMSI_3 after update")
            self.assert_bytes_equal(resp.data, new_imsi3, "IMSI_3 updated correctly")

            # Card should still be responsive (REFRESH issued internally)
            resp = self.card.select_mf()
            self.assert_sw(resp, 0x9000, "Card responsive after OTA update (REFRESH handled)")

            # Restore original
            resp = self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_IMSI_LIST)
            resp = self.card.update_binary(18, original_imsi3)
            self.assert_sw(resp, 0x9000, "Restore original IMSI_3")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_OTA_02(BaseTestCase):
    tc_id = "TC-OTA-02"
    title = "External file update of EF_Config triggers applet re-init"
    domain = "OTA"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read full EF_Config
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read full EF_Config")
            original_cfg = resp.data
            x = original_cfg[8]
            poll_offset = 9 + x

            if poll_offset >= len(original_cfg):
                raise AssertionError(f"Poll interval offset {poll_offset} out of range")

            # Change poll interval to 60s (0x3C)
            resp = self.card.update_binary(poll_offset, bytes([0x3C]))
            self.assert_sw(resp, 0x9000, f"Write poll interval = 3C (60s) at offset {poll_offset}")

            # Verify write
            resp = self.card.read_binary(poll_offset, 1)
            self.assert_sw(resp, 0x9000, "Read back poll interval byte")
            self.assert_byte(resp.data, 0, 0x3C, "Poll interval = 3C (60s)")

            # Card should remain responsive
            resp = self.card.select_mf()
            self.assert_sw(resp, 0x9000, "Card responsive after EF_Config update")

            # Restore original poll interval
            resp = self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.update_binary(poll_offset, bytes([original_cfg[poll_offset]]))
            self.assert_sw(resp, 0x9000, "Restore original poll interval")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
