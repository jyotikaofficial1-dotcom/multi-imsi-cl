import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
USIM_AID = "A0000000871002FF33FF018900000100"


class TC_5G_01(BaseTestCase):
    tc_id = "TC-5G-01"
    title = "EF_5GS3GPPNSC_List (4F53) — NAS security context ASN.1"
    domain = "5G Files"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F53")

            resp = self.card.read_binary(0, 0xFF)
            self.assert_sw(resp, 0x9000, "Read EF_5GS3GPPNSC_List (first 255 bytes)")
            data = resp.data

            # Slot 1 should start with ASN.1 SEQUENCE tag A0
            ok_tag = data[0] == 0xA0
            self._steps.append(StepResult(
                f"5GS3GPPNSC_1 ASN.1 tag = {data[0]:02X} (expected A0)",
                "", data[:10].hex().upper(),
                TestStatus.PASS if ok_tag else TestStatus.FAIL,
                "" if ok_tag else f"Expected A0, got {data[0]:02X}"
            ))
            if not ok_tag:
                raise AssertionError(f"5GS3GPPNSC tag {data[0]:#04x} != 0xA0")

            seq_len = data[1]
            seq_data = data[2:2 + seq_len]

            # Mandatory tags: 80 (ngKSI), 81 (keys), 82 (UL count), 83 (DL count)
            required_tags = {0x80, 0x81, 0x82, 0x83}
            found_tags = set()
            i = 0
            while i < len(seq_data) - 1:
                tag = seq_data[i]
                tlen = seq_data[i + 1]
                found_tags.add(tag)
                i += 2 + tlen

            for tag in required_tags:
                ok = tag in found_tags
                self._steps.append(StepResult(
                    f"Mandatory tag {tag:02X} present in 5GS3GPPNSC_1",
                    "", seq_data.hex().upper(),
                    TestStatus.PASS if ok else TestStatus.FAIL,
                    "" if ok else f"Tag {tag:02X} missing from NAS SC structure"
                ))
            if not required_tags.issubset(found_tags):
                missing = required_tags - found_tags
                raise AssertionError(f"Missing NAS SC tags: {[f'{t:02X}' for t in missing]}")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_5G_02(BaseTestCase):
    tc_id = "TC-5G-02"
    title = "EF_UAC_AIC_List (4F56) — 4 bytes per profile"
    domain = "5G Files"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F56")

            resp = self.card.read_binary(0, 40)
            self.assert_sw(resp, 0x9000, "Read EF_UAC_AIC_List (40 bytes)")
            data = resp.data

            ok_size = len(data) == 40
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 40)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)}"
            ))
            if not ok_size:
                raise AssertionError(f"EF_UAC_AIC_List wrong size: {len(data)}")

            uac1 = data[0:4]
            not_all_ff = uac1 != b'\xFF\xFF\xFF\xFF'
            self._steps.append(StepResult(
                f"UAC_AIC_1 = {uac1.hex().upper()} (not all FF if 5G profile active)",
                "", uac1.hex().upper(),
                TestStatus.PASS if not_all_ff else TestStatus.FAIL,
                "" if not_all_ff else "UAC_AIC_1 all FF — 5G profile may not be active"
            ))

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_5G_03(BaseTestCase):
    tc_id = "TC-5G-03"
    title = "EF_SUCI_Calc_Info_List (4F57) — ECIES public key 32 bytes"
    domain = "5G Files"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F57")

            resp = self.card.read_binary(0, 0xFF)
            self.assert_sw(resp, 0x9000, "Read EF_SUCI_Calc_Info_List (first 255 bytes)")
            data = resp.data

            # Expect TLV structure: A0 (protection scheme) A1 (public key)
            ok_tag = data[0] == 0xA0
            self._steps.append(StepResult(
                f"SUCI_Calc_Info_1 tag = {data[0]:02X} (expected A0)",
                "", data[:10].hex().upper(),
                TestStatus.PASS if ok_tag else TestStatus.FAIL,
                "" if ok_tag else f"Expected A0, got {data[0]:02X}"
            ))
            if not ok_tag:
                raise AssertionError(f"SUCI_Calc_Info tag {data[0]:#04x} != 0xA0")

            # Find A1 tag (public key container)
            i = 0
            pk_len = 0
            while i < len(data) - 1:
                tag = data[i]
                tlen = data[i + 1]
                if tag == 0xA1:
                    # Inside A1: tag 80 = key type, tag 81 = key bytes
                    inner = data[i + 2: i + 2 + tlen]
                    j = 0
                    while j < len(inner) - 1:
                        itag = inner[j]
                        ilen = inner[j + 1]
                        if itag == 0x81:
                            pk_len = ilen
                        j += 2 + ilen
                    break
                i += 2 + tlen

            ok_pk = pk_len == 32
            self._steps.append(StepResult(
                f"SUCI public key length = {pk_len} bytes (expected 32)",
                "", data[:40].hex().upper(),
                TestStatus.PASS if ok_pk else TestStatus.FAIL,
                "" if ok_pk else f"Public key length {pk_len} != 32"
            ))
            if not ok_pk:
                raise AssertionError(f"SUCI public key length {pk_len} != 32")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_5G_04(BaseTestCase):
    tc_id = "TC-5G-04"
    title = "5G files updated after IMSI switch"
    domain = "5G Files"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read UAC_AIC_2 from list (offset 4, length 4)
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F56")
            resp = self.card.read_binary(4, 4)
            self.assert_sw(resp, 0x9000, "Read UAC_AIC_2 from list (offset 4)")
            uac2 = resp.data

            # Trigger switch to index 2
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to IMSI index 2")

            # Verify EF_UAC_AIC in ADF USIM updated
            self.card.select_by_aid(USIM_AID)
            self.card.select_by_id("4F56")
            resp = self.card.read_binary(0, 4)
            self.assert_sw(resp, 0x9000, "Read EF_UAC_AIC from ADF USIM after switch")
            self.assert_bytes_equal(resp.data, uac2, "EF_UAC_AIC matches UAC_AIC_2 after switch")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_5G_05(BaseTestCase):
    tc_id = "TC-5G-05"
    title = "EF_Routing_Indicator_List (4F5A) — BCD format check"
    domain = "5G Files"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F5A")

            resp = self.card.read_binary(0, 40)
            self.assert_sw(resp, 0x9000, "Read EF_Routing_Indicator_List (40 bytes)")
            data = resp.data

            ok_size = len(data) == 40
            self._steps.append(StepResult(
                f"File size = {len(data)} bytes (expected 40)",
                "", "", TestStatus.PASS if ok_size else TestStatus.FAIL,
                "" if ok_size else f"Got {len(data)}"
            ))
            if not ok_size:
                raise AssertionError(f"EF_Routing_Indicator_List wrong size: {len(data)}")

            ri1 = data[0:4]
            not_all_ff = ri1 != b'\xFF\xFF\xFF\xFF'
            self._steps.append(StepResult(
                f"Routing_Indicator_1 = {ri1.hex().upper()} (not all FF if 5G active)",
                "", ri1.hex().upper(),
                TestStatus.PASS if not_all_ff else TestStatus.FAIL,
                "" if not_all_ff else "RI_1 all FF — 5G profile may not be active"
            ))

            # BCD digits: nibbles must be 0-9 or F (padding)
            for byte_idx, byte_val in enumerate(ri1):
                lo = byte_val & 0x0F
                hi = (byte_val >> 4) & 0x0F
                ok_lo = lo <= 9 or lo == 0xF
                ok_hi = hi <= 9 or hi == 0xF
                ok_byte = ok_lo and ok_hi
                self._steps.append(StepResult(
                    f"RI_1 byte {byte_idx}: {byte_val:02X} — BCD nibbles valid",
                    "", "", TestStatus.PASS if ok_byte else TestStatus.FAIL,
                    "" if ok_byte else f"Invalid BCD nibble in byte {byte_idx}: {byte_val:02X}"
                ))
                if not ok_byte:
                    raise AssertionError(f"Invalid BCD byte {byte_val:#04x} at offset {byte_idx}")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
