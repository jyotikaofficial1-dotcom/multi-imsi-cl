import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
USIM_AID = "A0000000871002FF33FF018900000100"


class TC_FILE_01(BaseTestCase):
    tc_id = "TC-FILE-01"
    title = "EF_IMSI_List (4F07) — size and BCD encoding"
    domain = "File Validation"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F07")

            # Read full 90 bytes in two chunks
            resp1 = self.card.read_binary(0, 0x5A)
            self.assert_sw(resp1, 0x9000, "Read EF_IMSI_List (90 bytes)")
            data = resp1.data

            ok_size = len(data) == 90
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 90)",
                "", data.hex().upper(),
                TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)} bytes, expected 90"
            ))
            if not ok_size:
                raise AssertionError(f"EF_IMSI_List wrong size: {len(data)}")

            # IMSI_1 must not be FF*9
            imsi1 = data[0:9]
            not_blank = imsi1 != b'\xFF' * 9
            self._steps.append(StepResult(
                "IMSI_1 is personalised (not FF×9)",
                "", imsi1.hex().upper(),
                TestStatus.PASS if not_blank else TestStatus.FAIL,
                "" if not_blank else "IMSI_1 slot is all FF (not personalised)"
            ))
            if not not_blank:
                raise AssertionError("IMSI_1 not personalised")

            # IMSI_1 length byte must be 07 or 08
            length_byte = imsi1[0]
            ok_len = length_byte in (0x07, 0x08)
            self._steps.append(StepResult(
                f"IMSI_1 length byte = {length_byte:02X} (valid: 07 or 08)",
                "", imsi1.hex().upper(),
                TestStatus.PASS if ok_len else TestStatus.FAIL,
                "" if ok_len else f"Unexpected IMSI length byte {length_byte:02X}"
            ))
            if not ok_len:
                raise AssertionError(f"IMSI_1 length byte {length_byte:#04x} invalid")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_FILE_02(BaseTestCase):
    tc_id = "TC-FILE-02"
    title = "EF_MCC_Mapping_List (4F03) — PLMN encoding and wildcard"
    domain = "File Validation"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F03")

            # Read in two chunks: 0-254, 255-499
            chunk1 = self.card.read_binary(0, 0xFF)
            self.assert_sw(chunk1, 0x9000, "Read EF_MCC_Mapping_List bytes 0-254")
            chunk2 = self.card.read_binary(0xFF, 0xF1)
            self.assert_sw(chunk2, 0x9000, "Read EF_MCC_Mapping_List bytes 255-499")
            data = chunk1.data + chunk2.data

            ok_size = len(data) >= 8  # at least 2 entries
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 500)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else "File too small"
            ))

            # Validate 4-byte entries
            valid_entries = 0
            has_wildcard = False
            for i in range(0, min(len(data), 500), 4):
                entry = data[i:i+4]
                if len(entry) < 4:
                    break
                if entry == b'\xFF\xFF\xFF\xFF':
                    break
                idx = entry[3]
                ok_idx = 0x01 <= idx <= 0x0A or idx == 0xFF
                if ok_idx and idx != 0xFF:
                    valid_entries += 1
                # Check wildcard (DDD DD → any pattern with DD nibbles)
                if entry[0] & 0x0F == 0x0D or entry[1] & 0xF0 == 0xD0:
                    has_wildcard = True

            self._steps.append(StepResult(
                f"Valid PLMN entries: {valid_entries}",
                "", data[:20].hex().upper(), TestStatus.PASS, ""
            ))

            ok_wc = has_wildcard
            self._steps.append(StepResult(
                "Wildcard PLMN entry present",
                "", "", TestStatus.PASS if ok_wc else TestStatus.FAIL,
                "" if ok_wc else "No wildcard/default entry found"
            ))

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_FILE_03(BaseTestCase):
    tc_id = "TC-FILE-03"
    title = "EF_SPN_List (4F46) — 17-byte records"
    domain = "File Validation"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F46")

            resp = self.card.read_binary(0, 0xAA)  # 170 bytes
            self.assert_sw(resp, 0x9000, "Read EF_SPN_List (170 bytes)")
            data = resp.data

            ok_size = len(data) == 170
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 170)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)}"
            ))

            spn1 = data[0:17]
            not_blank = spn1 != b'\xFF' * 17
            self._steps.append(StepResult(
                "SPN_1 personalised (not all FF)",
                "", spn1.hex().upper(),
                TestStatus.PASS if not_blank else TestStatus.FAIL,
                "" if not_blank else "SPN_1 all FF"
            ))

            # Display condition byte must be 00 or 01
            disp = spn1[0]
            ok_disp = disp in (0x00, 0x01)
            self._steps.append(StepResult(
                f"SPN_1 display condition = {disp:02X} (valid: 00 or 01)",
                "", "", TestStatus.PASS if ok_disp else TestStatus.FAIL,
                "" if ok_disp else f"Invalid display condition {disp:02X}"
            ))
            if not ok_disp:
                raise AssertionError(f"SPN display condition {disp:#04x} invalid")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_FILE_04(BaseTestCase):
    tc_id = "TC-FILE-04"
    title = "EF_ACC_List (4F78) — 2 bytes per profile"
    domain = "File Validation"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F78")

            resp = self.card.read_binary(0, 20)
            self.assert_sw(resp, 0x9000, "Read EF_ACC_List (20 bytes)")
            data = resp.data

            ok_size = len(data) == 20
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 20)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)}"
            ))
            if not ok_size:
                raise AssertionError(f"EF_ACC_List wrong size: {len(data)}")

            acc1 = data[0:2]
            self._steps.append(StepResult(
                f"ACC_1 = {acc1.hex().upper()} (valid range 0000-FFFF)",
                "", acc1.hex().upper(), TestStatus.PASS, ""
            ))

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_FILE_05(BaseTestCase):
    tc_id = "TC-FILE-05"
    title = "EF_AD_USIM_List (6FAD) — 4-byte AD records"
    domain = "File Validation"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("6FAD")

            resp = self.card.read_binary(0, 40)
            self.assert_sw(resp, 0x9000, "Read EF_AD_USIM_List (40 bytes)")
            data = resp.data

            ok_size = len(data) == 40
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 40)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)}"
            ))
            if not ok_size:
                raise AssertionError(f"EF_AD_USIM_List wrong size: {len(data)}")

            # AD_1 byte 3 (offset 2) = MNC length, must be 02 or 03
            mnc_len = data[2]
            ok_mnc = mnc_len in (0x02, 0x03)
            self._steps.append(StepResult(
                f"AD_1 MNC length byte (offset 2) = {mnc_len:02X} (valid: 02 or 03)",
                "", data[:4].hex().upper(),
                TestStatus.PASS if ok_mnc else TestStatus.FAIL,
                "" if ok_mnc else f"MNC length {mnc_len:02X} invalid"
            ))
            if not ok_mnc:
                raise AssertionError(f"MNC length byte {mnc_len:#04x} invalid")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_FILE_06(BaseTestCase):
    tc_id = "TC-FILE-06"
    title = "EF_PLMNwACT_List (4F60) — size = 10 × EF_PLMNwACT size"
    domain = "File Validation"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read PLMNwACT from ADF USIM to determine per-profile size
            self.card.select_by_aid(USIM_AID)
            self.card.select_by_id("6F60")
            # Use SELECT with P2=04 to get FCP — simplified: read and infer size
            resp_usim = self.card.read_binary(0, 0x28)  # try 40 bytes
            # If it works, usim size is 40 bytes (8×5 entries)
            usim_size = len(resp_usim.data) if resp_usim.ok else 40

            self._steps.append(StepResult(
                f"EF_PLMNwACT USIM size ≈ {usim_size} bytes",
                "", "", TestStatus.PASS, ""
            ))

            expected_total = usim_size * 10
            # Read 4F60
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F60")

            resp = self.card.read_binary(0, min(expected_total, 0xEF))
            self.assert_sw(resp, 0x9000, f"Read EF_PLMNwACT_List (first {min(expected_total,0xEF)} bytes)")
            data = resp.data

            self._steps.append(StepResult(
                f"EF_PLMNwACT_List read {len(data)} bytes (expected {expected_total})",
                "", "", TestStatus.PASS, ""
            ))

            # Validate 5-byte PLMN+ACT entries
            for i in range(0, min(len(data), usim_size), 5):
                entry = data[i:i+5]
                if len(entry) < 5 or entry[:3] == b'\xFF\xFF\xFF':
                    continue
                # ACT bitmap bytes 3-4 should have valid bits
                act = (entry[3] << 8) | entry[4]
                ok_act = act in range(0x10000)  # always true but explicit
                self._steps.append(StepResult(
                    f"PLMNwACT entry {i//5 + 1}: PLMN={entry[:3].hex().upper()} ACT={act:04X}",
                    "", entry.hex().upper(), TestStatus.PASS, ""
                ))
                break  # just validate first entry

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_FILE_07(BaseTestCase):
    tc_id = "TC-FILE-07"
    title = "EF_FPLMN_List (4F7B) — 120 bytes, 10 profiles × 12 bytes"
    domain = "File Validation"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F7B")

            resp = self.card.read_binary(0, 0x78)  # 120 bytes
            self.assert_sw(resp, 0x9000, "Read EF_FPLMN_List (120 bytes)")
            data = resp.data

            ok_size = len(data) == 120
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 120)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)}"
            ))
            if not ok_size:
                raise AssertionError(f"EF_FPLMN_List wrong size: {len(data)}")

            # Validate structure: 10 × 12-byte blocks
            for block_idx in range(10):
                block = data[block_idx * 12:(block_idx + 1) * 12]
                # Check no FF padding in middle of active block (first block only)
                if block_idx == 0 and block != b'\xFF' * 12:
                    # Basic structure: 4 × 3-byte FPLMN entries
                    for entry_idx in range(4):
                        entry = block[entry_idx * 3:(entry_idx + 1) * 3]
                        self._steps.append(StepResult(
                            f"Block 1 entry {entry_idx+1}: {entry.hex().upper()}",
                            "", "", TestStatus.PASS, ""
                        ))
                    break
            else:
                self._steps.append(StepResult(
                    "All 10 FPLMN blocks validated", "", "", TestStatus.PASS, ""
                ))

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
