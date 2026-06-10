import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult
from tests.card_config import MCC_MNC_HEX, MCC_IMSI_INDEX, PRIO_IMSI, IMSI_BY_INDEX

DF_MULTI = "7F305F1A"
EF_CONFIG = "4F01"
EF_IMSI_LIST = "4F07"
USIM_AID = "A0000000871002FF33FF018900000100"

# Decode MCC/MNC from card_config (e.g. "02F466" → MCC="204", MNC="66")
def _decode_plmn_hex(plmn_hex: str):
    b = bytes.fromhex(plmn_hex)
    mcc = f"{b[0] & 0x0F}{(b[0] >> 4) & 0x0F}{b[1] & 0x0F}"
    mnc2 = f"{b[2] & 0x0F}{(b[2] >> 4) & 0x0F}"
    mnc3_hi = (b[1] >> 4) & 0x0F
    mnc = (f"{mnc3_hi:X}{mnc2}" if mnc3_hi != 0xF else mnc2)
    return mcc, mnc

CARD_MCC, CARD_MNC = _decode_plmn_hex(MCC_MNC_HEX)


class TC_AUTO_01(BaseTestCase):
    tc_id = "TC-AUTO-01"
    title = "Normal service — PLMN match → switch to priority IMSI"
    domain = "Auto Switch"
    priority = "P1"
    description = (
        f"Sends LOCATION_STATUS Normal Service with card PLMN ({MCC_MNC_HEX}), "
        f"then reads EF_Config (4F01) byte 2 to assert the active index is "
        f"{MCC_IMSI_INDEX:02X} and verifies EF_IMSI in ADF USIM matches the expected profile."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read expected IMSI from list
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_IMSI_LIST)
            resp = self.card.read_binary((MCC_IMSI_INDEX - 1) * 9, 9)
            self.assert_sw(resp, 0x9000, f"Read IMSI[{MCC_IMSI_INDEX}] from EF_IMSI_List")
            expected_imsi = resp.data

            # Trigger Normal Service
            resp = self.card.send_location_status(CARD_MCC, CARD_MNC, 0)
            self.assert_sw(resp, 0x9000, f"LOCATION_STATUS Normal MCC={CARD_MCC} MNC={CARD_MNC}")

            # Verify active IMSI index switched
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, MCC_IMSI_INDEX,
                             f"Active IMSI index = {MCC_IMSI_INDEX:02X}")

            # Verify EF_IMSI in ADF USIM
            self.card.select_by_aid(USIM_AID)
            self.card.select_by_id("6F07")
            resp = self.card.read_binary(0, 9)
            self.assert_sw(resp, 0x9000, "Read EF_IMSI from ADF USIM")
            self.assert_bytes_equal(resp.data, expected_imsi, "EF_IMSI matches expected profile")

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
    description = (
        "Records the current active index from EF_Config (4F01) byte 2, "
        "sends a second LOCATION_STATUS for the same PLMN, then re-reads "
        "byte 2 to confirm the index is unchanged."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read current active IMSI index")
            current_idx = resp.data[0]

            resp = self.card.send_location_status(CARD_MCC, CARD_MNC, 0)
            self.assert_sw(resp, 0x9000, f"LOCATION_STATUS same PLMN MCC={CARD_MCC} MNC={CARD_MNC}")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after repeat event")
            self.assert_byte(resp.data, 0, current_idx,
                             f"Active index unchanged = {current_idx:02X}")

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
    description = (
        f"Sends LOCATION_STATUS Limited Service (service_type=1) with the card PLMN, "
        f"then reads EF_Config (4F01) byte 2 to assert the active IMSI index = {PRIO_IMSI:02X} "
        f"(priority IMSI)."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status(CARD_MCC, CARD_MNC, 1)
            self.assert_sw(resp, 0x9000, f"LOCATION_STATUS Limited Service MCC={CARD_MCC}")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, PRIO_IMSI,
                             f"Active IMSI index = {PRIO_IMSI:02X} (priority)")

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
    description = (
        f"Sends LOCATION_STATUS Normal Service with unknown PLMN MCC=999/MNC=01, "
        f"then reads EF_Config (4F01) byte 2 to assert the applet fell back to "
        f"priority/default index {PRIO_IMSI:02X}."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("999", "01", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS unknown PLMN MCC=999/MNC=01")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, PRIO_IMSI,
                             f"Active IMSI index = {PRIO_IMSI:02X} (default/wildcard)")

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
    description = (
        "Writes 00 to EF_Config (4F01) offset 1 to disable automatic mode, "
        "fires a LOCATION_STATUS event, confirms EF_Config byte 2 (active index) "
        "is unchanged; restores auto mode to 01 afterwards."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)

            resp = self.card.update_binary(1, bytes([0x00]))
            self.assert_sw(resp, 0x9000, "Disable automatic mode (write 00 to offset 1)")

            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read current active IMSI index")
            current_idx = resp.data[0]

            resp = self.card.send_location_status(CARD_MCC, CARD_MNC, 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS (auto mode off)")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after event")
            self.assert_byte(resp.data, 0, current_idx,
                             "Active index unchanged (auto mode off)")

            resp = self.card.update_binary(1, bytes([0x01]))
            self.assert_sw(resp, 0x9000, "Re-enable automatic mode")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
