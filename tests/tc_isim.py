import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult

DF_MULTI = "7F305F1A"
USIM_AID = "A0000000871002FF33FF018900000100"


class TC_ISIM_01(BaseTestCase):
    tc_id = "TC-ISIM-01"
    title = "EF_IMPI_List (4F32) — IMS private identity TLV encoding"
    domain = "ISIM Files"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F32")

            # Read first 255 bytes
            resp = self.card.read_binary(0, 0xFF)
            self.assert_sw(resp, 0x9000, "Read EF_IMPI_List (first 255 bytes)")
            data = resp.data

            # IMPI_1 should start with TLV tag 80
            impi1_tag = data[0] if data else 0xFF
            ok_tag = impi1_tag == 0x80
            self._steps.append(StepResult(
                f"IMPI_1 TLV tag = {impi1_tag:02X} (expected 80)",
                "", data[:10].hex().upper(),
                TestStatus.PASS if ok_tag else TestStatus.FAIL,
                "" if ok_tag else f"Expected tag 80, got {impi1_tag:02X}"
            ))
            if not ok_tag:
                raise AssertionError(f"IMPI_1 TLV tag {impi1_tag:#04x} != 0x80")

            impi_len = data[1]
            impi_nai = data[2:2 + impi_len]

            ok_not_blank = impi_nai != b'\xFF' * impi_len
            self._steps.append(StepResult(
                "IMPI_1 NAI is personalised",
                "", impi_nai[:20].hex().upper(),
                TestStatus.PASS if ok_not_blank else TestStatus.FAIL,
                "" if ok_not_blank else "IMPI_1 NAI all FF"
            ))

            # NAI must contain '@'
            has_at = b'@' in impi_nai
            self._steps.append(StepResult(
                f"IMPI_1 NAI contains '@' character",
                "", impi_nai.decode('ascii', errors='replace'),
                TestStatus.PASS if has_at else TestStatus.FAIL,
                "" if has_at else "NAI missing '@' separator"
            ))
            if not has_at:
                raise AssertionError("IMPI NAI missing '@' — invalid format")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_ISIM_02(BaseTestCase):
    tc_id = "TC-ISIM-02"
    title = "EF_DOMAIN_List (4F33) — home network domain FQDN"
    domain = "ISIM Files"
    priority = "P2"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F33")

            resp = self.card.read_binary(0, 0xFF)
            self.assert_sw(resp, 0x9000, "Read EF_DOMAIN_List (first 255 bytes)")
            data = resp.data

            # DOMAIN_1 TLV tag 80
            ok_tag = data[0] == 0x80
            self._steps.append(StepResult(
                f"DOMAIN_1 TLV tag = {data[0]:02X} (expected 80)",
                "", data[:10].hex().upper(),
                TestStatus.PASS if ok_tag else TestStatus.FAIL,
                "" if ok_tag else f"Tag {data[0]:02X} != 80"
            ))
            if not ok_tag:
                raise AssertionError(f"DOMAIN_1 tag {data[0]:#04x} != 0x80")

            dom_len = data[1]
            domain_bytes = data[2:2 + dom_len]

            try:
                domain_str = domain_bytes.decode('ascii')
            except UnicodeDecodeError:
                raise AssertionError("DOMAIN_1 is not printable ASCII")

            ok_fqdn = '.' in domain_str and '\x00' not in domain_str and ' ' not in domain_str
            self._steps.append(StepResult(
                f"DOMAIN_1 = '{domain_str}' (valid FQDN)",
                "", domain_str,
                TestStatus.PASS if ok_fqdn else TestStatus.FAIL,
                "" if ok_fqdn else f"Invalid FQDN: '{domain_str}'"
            ))
            if not ok_fqdn:
                raise AssertionError(f"DOMAIN_1 '{domain_str}' not a valid FQDN")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_ISIM_03(BaseTestCase):
    tc_id = "TC-ISIM-03"
    title = "ISIM files updated after IMSI switch"
    domain = "ISIM Files"
    priority = "P1"

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        try:
            # Read IMPI_2 from list EF
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F32")
            resp = self.card.read_binary(0, 4)
            self.assert_sw(resp, 0x9000, "Read IMPI_1 TLV header from list")
            impi_slot_size = resp.data[1] + 2 if resp.data[0] == 0x80 else 30

            resp = self.card.read_binary(impi_slot_size, impi_slot_size)
            self.assert_sw(resp, 0x9000, "Read IMPI_2 TLV from list EF")
            impi2 = resp.data

            # Trigger switch to index 2
            resp = self.card.send_location_status("424", "02", 0)
            self.assert_sw(resp, 0x9000, "Trigger switch to IMSI index 2")

            # Read EF_Config to get ISIM AID
            self.card.select_by_path(DF_MULTI)
            self.card.select_by_id("4F01")
            resp = self.card.read_binary(0, 50)
            self.assert_sw(resp, 0x9000, "Read EF_Config to locate ISIM AID")
            cfg = resp.data
            x = cfg[8]

            # ISIM AID at offset X+22 (0-based x+21) length + data
            isim_len_off = x + 21
            if isim_len_off < len(cfg):
                isim_len = cfg[isim_len_off]
                isim_aid = cfg[isim_len_off + 1: isim_len_off + 1 + isim_len]
            else:
                # Fall back to a standard ISIM AID pattern
                isim_aid = bytes.fromhex("A0000000871004FF33FF018900000100")

            # Select ADF ISIM and read EF_IMPI (6F02)
            resp = self.card.select_by_aid(isim_aid.hex())
            self.assert_sw(resp, 0x9000, f"Select ADF ISIM (AID={isim_aid.hex().upper()})")

            self.card.select_by_id("6F02")
            resp = self.card.read_binary(0, impi_slot_size)
            self.assert_sw(resp, 0x9000, "Read EF_IMPI from ADF ISIM after switch")
            self.assert_bytes_equal(resp.data, impi2, "EF_IMPI matches IMPI_2 after switch")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
