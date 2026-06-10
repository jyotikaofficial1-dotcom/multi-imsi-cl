"""
EF MCC Mapping List (4F03) test cases.

File structure: 500 bytes transparent, each entry = 4 bytes:
    Bytes 0-2: PLMN in GSM 04.08 encoding
    Byte    3: Mapped IMSI Index (1-based)

Wildcard convention: nibble value 0xD in PLMN bytes matches any digit.

Algorithm (from spec §2.2 and applet behaviour):
  Normal  service: find first PLMN match → switch to that IMSI index.
  Limited service: find first PLMN match (priority IMSI), then scan forward
                   for another entry with same MCC → switch to that (preferred
                   IMSI).  If no second entry, fall back to PRIO_IMSI (index 1).
  No match at all: fall back to default wildcard entry (DDDDDD) → PRIO_IMSI.

Personalization data (Variables.txt):
  46D2DD01  Burundi        642/DD → IMSI 1
  43D6DD01  Cayman Islands 346/DD → IMSI 1
  26D3DD01  CAR            623/DD → IMSI 1
  24D4DD02  UAE            424/DD → IMSI 2
  34D1DD02  UAE            431/DD → IMSI 2
  64F03002  China          460/03 → IMSI 2  (exact MNC)
  64F05003  China          460/05 → IMSI 3  (exact MNC)
  64D0DD01  China          460/DD → IMSI 1  (wildcard MNC)
  04D4DD03  India          404/DD → IMSI 3  (1st India entry)
  04D4DD02  India          404/DD → IMSI 2  (2nd India entry – preferred on limited)
  02D4DD03  Netherlands    204/DD → IMSI 3
  DDDDDD01  Default        DDD/DD → IMSI 1
"""

import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult
from tests.card_config import PRIO_IMSI, MAX_PROFILES

DF_MULTI    = "7F305F1A"
EF_CONFIG   = "4F01"
EF_MCC_LIST = "4F03"

# ---- Expected raw bytes for the 12 personalised entries ------------------
MCC_LIST_ENTRIES = bytes.fromhex(
    "46D2DD01"   # entry  1 – Burundi        642/DD → 1
    "43D6DD01"   # entry  2 – Cayman Islands 346/DD → 1
    "26D3DD01"   # entry  3 – CAR            623/DD → 1
    "24D4DD02"   # entry  4 – UAE            424/DD → 2
    "34D1DD02"   # entry  5 – UAE            431/DD → 2
    "64F03002"   # entry  6 – China          460/03 → 2
    "64F05003"   # entry  7 – China          460/05 → 3
    "64D0DD01"   # entry  8 – China          460/DD → 1
    "04D4DD03"   # entry  9 – India          404/DD → 3
    "04D4DD02"   # entry 10 – India          404/DD → 2  (limited-service preferred)
    "02D4DD03"   # entry 11 – Netherlands    204/DD → 3
    "DDDDDD01"   # entry 12 – Default        DDD/DD → 1
)

# IMSI index expected per scenario (derived from table above)
_IDX_UAE_NORMAL       = 2   # 424/DD entry 4
_IDX_UAE_ALT_NORMAL   = 2   # 431/DD entry 5
_IDX_CHINA_EXACT_1    = 2   # 460/03 entry 6
_IDX_CHINA_EXACT_2    = 3   # 460/05 entry 7
_IDX_CHINA_WILDCARD   = 1   # 460/DD entry 8  (any other 460 MNC)
_IDX_INDIA_NORMAL     = 3   # 404/DD entry 9  (first India entry)
_IDX_INDIA_PREFERRED  = 2   # 404/DD entry 10 (second India entry – limited svc)
_IDX_NL_NORMAL        = 3   # 204/DD entry 11
_IDX_DEFAULT          = 1   # DDDDDD entry 12 / PRIO_IMSI


def _read_active_index(test_obj) -> int:
    """Select DF_MULTI/EF_CONFIG and return the active IMSI index (byte offset 2)."""
    test_obj.card.select_by_path(DF_MULTI)
    test_obj.card.select_by_id(EF_CONFIG)
    resp = test_obj.card.read_binary(2, 1)
    test_obj.assert_sw(resp, 0x9000, "Read active IMSI index from EF_Config")
    return resp.data[0]


def _force_normal_service(test_obj, mcc: str, mnc: str) -> None:
    """Send a Normal Service event to put the applet into a known starting state."""
    resp = test_obj.card.send_location_status(mcc, mnc, 0)
    test_obj.assert_sw(resp, 0x9000, f"Setup: Normal Service MCC={mcc} MNC={mnc}")


# ---------------------------------------------------------------------------
# TC-MCC-01  File structure validation
# ---------------------------------------------------------------------------

class TC_MCC_01(BaseTestCase):
    tc_id    = "TC-MCC-01"
    title    = "EF_MCC_List (4F03) — file size and first entry structure"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Selects EF MCC Mapping List (4F03) under DF Multi-IMSI (7F30/5F1A) and reads "
        "48 bytes (12 entries × 4 bytes).  Asserts SW=9000, verifies the total read "
        "length equals 48 and that the first entry matches the Burundi wildcard entry "
        "46D2DD01 exactly."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_MCC_LIST)
            resp = self.card.read_binary(0, 48)
            self.assert_sw(resp, 0x9000, "Read first 48 bytes of EF_MCC_List")

            # Total bytes returned
            actual_len = len(resp.data)
            if actual_len < 48:
                raise AssertionError(
                    f"Expected ≥48 bytes from 4F03, got {actual_len}"
                )
            self._steps.append(StepResult(
                "File length check", "", f"{actual_len} bytes", TestStatus.PASS, ""
            ))

            # First entry must equal 46D2DD01
            first_entry = resp.data[:4]
            expected = bytes.fromhex("46D2DD01")
            self.assert_bytes_equal(first_entry, expected, "First entry = 46D2DD01 (Burundi 642/DD → IMSI 1)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-02  Normal service — all 12 entries verified sequentially
# ---------------------------------------------------------------------------

class TC_MCC_02(BaseTestCase):
    tc_id    = "TC-MCC-02"
    title    = "EF_MCC_List (4F03) — verify all 12 personalised entries"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Reads all 48 bytes of EF_MCC_List (4F03) and verifies every 4-byte entry "
        "matches the expected personalisation data: 12 entries covering Burundi, "
        "Cayman Islands, CAR, UAE (×2), China (×3), India (×2), Netherlands and the "
        "default wildcard DDDDDD."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_MCC_LIST)
            resp = self.card.read_binary(0, 48)
            self.assert_sw(resp, 0x9000, "Read 48 bytes of EF_MCC_List")
            self.assert_bytes_equal(resp.data[:48], MCC_LIST_ENTRIES,
                                    "All 12 entries match expected personalisation")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-03  Normal service — exact PLMN match (China 460/03 → IMSI 2)
# ---------------------------------------------------------------------------

class TC_MCC_03(BaseTestCase):
    tc_id    = "TC-MCC-03"
    title    = "Normal service — exact PLMN match: China 460/03 → IMSI 2"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=460 MNC=03 (China).  "
        "Entry 6 in EF_MCC_List (64F03002) is the first exact match → IMSI index 2.  "
        "Asserts EF_Config byte 2 = 02 after the event."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("460", "03", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=460 MNC=03")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_CHINA_EXACT_1,
                             f"Active IMSI index = {_IDX_CHINA_EXACT_1:02X} (China 460/03)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-04  Normal service — exact PLMN match (China 460/05 → IMSI 3)
# ---------------------------------------------------------------------------

class TC_MCC_04(BaseTestCase):
    tc_id    = "TC-MCC-04"
    title    = "Normal service — exact PLMN match: China 460/05 → IMSI 3"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=460 MNC=05 (China).  "
        "Entry 7 (64F05003) is an exact match → IMSI index 3.  Asserts EF_Config "
        "byte 2 = 03 after the event."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("460", "05", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=460 MNC=05")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_CHINA_EXACT_2,
                             f"Active IMSI index = {_IDX_CHINA_EXACT_2:02X} (China 460/05)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-05  Normal service — wildcard MNC match (UAE 424/01 → IMSI 2)
# ---------------------------------------------------------------------------

class TC_MCC_05(BaseTestCase):
    tc_id    = "TC-MCC-05"
    title    = "Normal service — wildcard MNC match: UAE 424/01 → IMSI 2"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=424 MNC=01 (UAE).  "
        "Entry 4 (24D4DD02) stores MNC=DD (wildcard) which matches any MNC → IMSI 2.  "
        "Asserts EF_Config byte 2 = 02."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("424", "01", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=424 MNC=01")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_UAE_NORMAL,
                             f"Active IMSI index = {_IDX_UAE_NORMAL:02X} (UAE 424/DD wildcard)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-06  Normal service — wildcard MNC (Netherlands 204/66 → IMSI 3)
# ---------------------------------------------------------------------------

class TC_MCC_06(BaseTestCase):
    tc_id    = "TC-MCC-06"
    title    = "Normal service — wildcard MNC match: Netherlands 204/66 → IMSI 3"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=204 MNC=66 (Netherlands — the "
        "card's own PLMN).  Entry 11 (02D4DD03) stores MNC=DD (wildcard) which matches "
        "→ IMSI 3.  This also verifies that MCC_IMSI_INDEX=3 in card_config is correct."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("204", "66", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=204 MNC=66")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_NL_NORMAL,
                             f"Active IMSI index = {_IDX_NL_NORMAL:02X} (Netherlands 204/DD wildcard)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-07  Normal service — default wildcard fallback (unknown PLMN → IMSI 1)
# ---------------------------------------------------------------------------

class TC_MCC_07(BaseTestCase):
    tc_id    = "TC-MCC-07"
    title    = "Normal service — no match, default wildcard DDDDDD → IMSI 1"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=999 MNC=01 (not in list).  "
        "No specific entry matches, but the last entry DDDDDD01 is the catch-all "
        "default → IMSI 1.  Asserts EF_Config byte 2 = 01."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("999", "01", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=999 MNC=01 (unknown)")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_DEFAULT,
                             f"Active IMSI index = {_IDX_DEFAULT:02X} (default/wildcard)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-08  Limited service — second entry same PLMN (India 404 → IMSI 2)
# ---------------------------------------------------------------------------

class TC_MCC_08(BaseTestCase):
    tc_id    = "TC-MCC-08"
    title    = "Limited service — second entry for same PLMN: India 404/DD → IMSI 2"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sets up Normal Service for India (MCC=404) so IMSI 3 is active (entry 9 = "
        "priority for India).  Then sends Limited Service for the same PLMN.  "
        "The applet scans forward from entry 9 and finds entry 10 (04D4DD02) with the "
        "same PLMN → preferred IMSI index 2.  Asserts EF_Config byte 2 = 02."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Setup: ensure we are on the priority IMSI for India (IMSI 3)
            _force_normal_service(self, "404", "01")

            idx_before = _read_active_index(self)
            if idx_before != _IDX_INDIA_NORMAL:
                raise AssertionError(
                    f"Setup failed: expected active IMSI {_IDX_INDIA_NORMAL}, "
                    f"got {idx_before}"
                )

            # Trigger Limited Service for India
            resp = self.card.send_location_status("404", "01", 1)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Limited MCC=404 MNC=01")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after Limited Service")
            self.assert_byte(resp.data, 0, _IDX_INDIA_PREFERRED,
                             f"Active IMSI index = {_IDX_INDIA_PREFERRED:02X} "
                             f"(India preferred — 2nd entry in MCC list)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-09  Limited service — next entry for same MCC (China 460/03 → IMSI 3)
# ---------------------------------------------------------------------------

class TC_MCC_09(BaseTestCase):
    tc_id    = "TC-MCC-09"
    title    = "Limited service — next entry same MCC: China 460/03 priority=2, preferred=3"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends Normal Service MCC=460 MNC=03 → IMSI 2 (entry 6, priority).  "
        "Then sends Limited Service MCC=460 MNC=03.  The applet scans forward from "
        "entry 6 and finds entry 7 (64F05003) which shares MCC=460 → preferred IMSI 3.  "
        "Asserts EF_Config byte 2 = 03."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Setup: switch to priority IMSI for China 460/03
            _force_normal_service(self, "460", "03")

            idx_before = _read_active_index(self)
            if idx_before != _IDX_CHINA_EXACT_1:
                raise AssertionError(
                    f"Setup failed: expected active IMSI {_IDX_CHINA_EXACT_1}, "
                    f"got {idx_before}"
                )

            # Trigger Limited Service for China 460/03
            resp = self.card.send_location_status("460", "03", 1)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Limited MCC=460 MNC=03")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after Limited Service")
            self.assert_byte(resp.data, 0, _IDX_CHINA_EXACT_2,
                             f"Active IMSI index = {_IDX_CHINA_EXACT_2:02X} "
                             f"(China preferred — next MCC=460 entry)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-10  Limited service — no second entry → fallback to PRIO_IMSI
# ---------------------------------------------------------------------------

class TC_MCC_10(BaseTestCase):
    tc_id    = "TC-MCC-10"
    title    = "Limited service — no second entry for PLMN: UAE 424 → fallback IMSI 1"
    domain   = "MCC List"
    priority = "P1"
    description = (
        "Sends Normal Service MCC=424 → IMSI 2 (entry 4 = priority for UAE).  "
        "Then sends Limited Service MCC=424.  Only one UAE 424 entry exists in the "
        "MCC list — no preferred IMSI found by forward scan.  The applet falls back to "
        f"PRIO_IMSI = {PRIO_IMSI}.  Asserts EF_Config byte 2 = {PRIO_IMSI:02X}."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Setup: switch to priority IMSI for UAE 424
            _force_normal_service(self, "424", "01")

            idx_before = _read_active_index(self)
            if idx_before != _IDX_UAE_NORMAL:
                raise AssertionError(
                    f"Setup failed: expected active IMSI {_IDX_UAE_NORMAL}, "
                    f"got {idx_before}"
                )

            # Trigger Limited Service for UAE 424
            resp = self.card.send_location_status("424", "01", 1)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Limited MCC=424 MNC=01")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index after Limited Service")
            self.assert_byte(resp.data, 0, PRIO_IMSI,
                             f"Active IMSI index = {PRIO_IMSI:02X} "
                             f"(no second UAE entry → fallback to PRIO_IMSI)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-11  China wildcard (460/DD) entry — any non-mapped 460 MNC → IMSI 1
# ---------------------------------------------------------------------------

class TC_MCC_11(BaseTestCase):
    tc_id    = "TC-MCC-11"
    title    = "Normal service — China 460/DD wildcard entry: MNC=99 → IMSI 1"
    domain   = "MCC List"
    priority = "P2"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=460 MNC=99 (a China MNC not "
        "listed as 03 or 05).  The exact entries (64F03002, 64F05003) do not match; "
        "entry 8 (64D0DD01, MNC=DD wildcard) matches → IMSI 1.  "
        "Asserts EF_Config byte 2 = 01."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("460", "99", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=460 MNC=99")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_CHINA_WILDCARD,
                             f"Active IMSI index = {_IDX_CHINA_WILDCARD:02X} "
                             f"(China 460/DD wildcard)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


# ---------------------------------------------------------------------------
# TC-MCC-12  Second UAE entry (431/DD) normal service → IMSI 2
# ---------------------------------------------------------------------------

class TC_MCC_12(BaseTestCase):
    tc_id    = "TC-MCC-12"
    title    = "Normal service — second UAE entry: MCC=431 MNC=01 → IMSI 2"
    domain   = "MCC List"
    priority = "P2"
    description = (
        "Sends LOCATION_STATUS Normal Service with MCC=431 MNC=01 (UAE second MCC "
        "group).  Entry 5 (34D1DD02) with MNC=DD wildcard matches → IMSI 2.  "
        "Asserts EF_Config byte 2 = 02."
    )

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            resp = self.card.send_location_status("431", "01", 0)
            self.assert_sw(resp, 0x9000, "LOCATION_STATUS Normal MCC=431 MNC=01")

            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id(EF_CONFIG)
            resp = self.card.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index")
            self.assert_byte(resp.data, 0, _IDX_UAE_ALT_NORMAL,
                             f"Active IMSI index = {_IDX_UAE_ALT_NORMAL:02X} (UAE 431/DD)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
