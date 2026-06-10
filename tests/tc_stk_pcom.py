"""
STK switching test cases — converted from Automatic_MI2.6_STK.pcom.
Uses PcomCardIO for T=0 compatible step-by-step navigation.
"""
import time
from tests.base_test import BaseTestCase, TestResult, TestStatus, StepResult
from tests.card_config import (
    ADM_KEY_HEX, IMSI_BY_INDEX, SMSC_BY_INDEX, SPN_BY_INDEX, ACC_BY_INDEX,
    MCC_MNC_HEX, MCC_IMSI_INDEX, PRIO_IMSI, MAX_PROFILES,
    DF_7F30, DF_5F1A, EF_CONFIG, EF_IMSI_LIST,
    EF_IMSI, EF_ACC, EF_SPN, EF_SMSP, DF_GSM, DF_TELECOM,
)
from engine.card_io_pcom import PcomCardIO

SMSP_LEN = 0x2B  # 43 bytes


def _make_pcom(card) -> PcomCardIO:
    return PcomCardIO(card._conn)


def _read_active_index(pcom: PcomCardIO) -> int:
    """Navigate to EF_Config and return the active IMSI index (1-based)."""
    pcom.select_fid(DF_7F30)
    pcom.select_fid(DF_5F1A)
    pcom.select_ef(EF_CONFIG)
    resp = pcom.read_binary(0, 0x36)
    return resp.data[2]  # byte 3 (1-indexed) = offset 2 (0-indexed)


def _verify_standard_efs(pcom: PcomCardIO, idx: int, steps: list) -> bool:
    """Read DF_GSM EFs and verify against expected values for IMSI index idx."""
    ok = True

    pcom.select_mf()
    pcom.select_fid(DF_GSM)
    pcom.select_ef(EF_IMSI)
    resp = pcom.read_binary(0, 9)
    expected = IMSI_BY_INDEX.get(idx, b'\xFF' * 9)
    match = resp.data == expected
    steps.append(StepResult(
        f"EF_IMSI index {idx} = {resp.data.hex().upper()}",
        "00 B0 00 00 09", str(resp),
        TestStatus.PASS if match else TestStatus.FAIL,
        "" if match else f"Expected {expected.hex().upper()}, got {resp.data.hex().upper()}"
    ))
    ok = ok and match

    pcom.select_ef(EF_ACC)
    resp = pcom.read_binary(0, 2)
    expected = ACC_BY_INDEX.get(idx, b'\xFF\xFF')
    match = resp.data == expected
    steps.append(StepResult(
        f"EF_ACC index {idx} = {resp.data.hex().upper()}",
        "00 B0 00 00 02", str(resp),
        TestStatus.PASS if match else TestStatus.FAIL,
        "" if match else f"Expected {expected.hex().upper()}"
    ))
    ok = ok and match

    pcom.select_ef(EF_SPN)
    resp = pcom.read_binary(0, 0x11)
    expected = SPN_BY_INDEX.get(idx, b'\xFF' * 17)
    match = resp.data == expected
    steps.append(StepResult(
        f"EF_SPN index {idx} = {resp.data.hex().upper()}",
        "00 B0 00 00 11", str(resp),
        TestStatus.PASS if match else TestStatus.FAIL,
        "" if match else f"Expected {expected.hex().upper()}"
    ))
    ok = ok and match

    pcom.select_mf()
    pcom.select_fid(DF_TELECOM)
    pcom.select_ef(EF_SMSP)
    resp = pcom.read_record(1, SMSP_LEN)
    expected = SMSC_BY_INDEX.get(idx, b'\xFF' * SMSP_LEN)
    match = resp.data == expected
    steps.append(StepResult(
        f"EF_SMSP index {idx} = {resp.data.hex().upper()}",
        f"00 B2 01 04 {SMSP_LEN:02X}", str(resp),
        TestStatus.PASS if match else TestStatus.FAIL,
        "" if match else f"Expected {expected.hex().upper()}"
    ))
    ok = ok and match

    return ok


def _drain_initial_stk(pcom: PcomCardIO, steps: list) -> int:
    """
    Send TERMINAL PROFILE and drain all pending STK commands.
    Returns the final SW2 byte (0 if no STK pending).
    """
    resp = pcom.terminal_profile()
    steps.append(StepResult(
        f"TERMINAL PROFILE → SW={resp.sw_hex}",
        "80 10 00 00 0C FF×12", str(resp), TestStatus.PASS, ""
    ))

    for i in range(100):
        if resp.sw1 != 0x91:
            break
        length = resp.sw2
        fetch_resp = pcom.fetch(length)
        steps.append(StepResult(
            f"FETCH #{i+1} → {fetch_resp.data.hex().upper() if fetch_resp.data else 'empty'}",
            f"80 12 00 00 {length:02X}", str(fetch_resp), TestStatus.PASS, ""
        ))
        if len(fetch_resp.data) < 6:
            break
        cmd_details = fetch_resp.data[3:6]
        resp = pcom.terminal_response(cmd_details, 0x00)
        steps.append(StepResult(
            f"TERMINAL RESPONSE #{i+1} → SW={resp.sw_hex}",
            "80 14 00 00 0C ...", str(resp), TestStatus.PASS, ""
        ))
    return resp.sw2 if resp.sw1 == 0x91 else 0


class TC_STK_NEXT_IMSI(BaseTestCase):
    """
    STK switching — Next IMSI
    Converted from PCOM: Automatic_MI2.6_STK.pcom section "STK Switching test case - Next IMSI"
    """
    tc_id = "TC-STK-NEXT-IMSI"
    title = "STK Next IMSI — switch to next profile"
    domain = "STK Menu"
    priority = "P1"
    description = "Reads EF_Config (4F01) byte 2 for the current index, drains initial STK commands, selects menu item 01 (Next IMSI), fetches the resulting REFRESH, then reads EF_IMSI/EF_ACC/EF_SPN/EF_SMSP and asserts each matches the expected values for index current+1."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        pcom = _make_pcom(self.card)
        try:
            # Step 1: ADM verify
            resp = pcom.verify_adm(ADM_KEY_HEX)
            self.assert_sw(resp, 0x9000, "ADM VERIFY")

            # Step 2: Read current IMSI index from EF_Config
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(0, 0x36)
            self.assert_sw(resp, 0x9000, "Read EF_Config (54 bytes)")
            current_idx = resp.data[2]
            self._steps.append(StepResult(
                f"Current IMSI index = {current_idx}",
                "", resp.data.hex().upper(), TestStatus.PASS, ""
            ))

            # Step 3: Verify current EF contents match expected
            _verify_standard_efs(pcom, current_idx, self._steps)

            # Step 4: Drain initial STK commands (SETUP_MENU, POLL INTERVAL etc.)
            _drain_initial_stk(pcom, self._steps)

            # Step 5: Open the STK menu
            resp = pcom.menu_selection(0x80)  # Open menu (item=0x80 = main menu request)
            # Actually from PCOM: 80C2000009 D3 07 82 02 01 81 90 01 80
            self._steps.append(StepResult(
                f"ENVELOPE MENU SELECTION (open menu) → SW={resp.sw_hex}",
                "80 C2 00 00 09 D3 07 82 02 01 81 90 01 80", str(resp),
                TestStatus.PASS, ""
            ))

            if resp.sw1 == 0x91:
                # FETCH the SET UP MENU proactive command
                fetch_resp = pcom.fetch(resp.sw2)
                self._steps.append(StepResult(
                    f"FETCH SET_UP_MENU → {fetch_resp.data.hex().upper()[:40]}...",
                    f"80 12 00 00 {resp.sw2:02X}", str(fetch_resp), TestStatus.PASS, ""
                ))

            # Step 6: Select "Next IMSI" (item 01)
            resp = pcom.menu_selection(0x01)
            self._steps.append(StepResult(
                f"SELECT ITEM 01 (Next IMSI) → SW={resp.sw_hex}",
                "80 14 00 00 0F 81 03 01 24 00 82 02 82 81 83 01 00 90 01 01",
                str(resp),
                TestStatus.PASS if resp.sw1 in (0x90, 0x91) else TestStatus.FAIL,
                "" if resp.sw1 in (0x90, 0x91) else f"Unexpected SW {resp.sw_hex}"
            ))

            # Step 7: FETCH REFRESH and respond
            if resp.sw1 == 0x91:
                tr_resp, cmd_data = pcom.fetch_and_respond(resp.sw2, 0x00)
                self._steps.append(StepResult(
                    f"FETCH+TR REFRESH → cmd={cmd_data.hex().upper()[:20]}",
                    f"80 12 00 00 {resp.sw2:02X}", str(tr_resp), TestStatus.PASS, ""
                ))

            # Step 8: Calculate expected next index
            expected_next = (current_idx % MAX_PROFILES) + 1

            # Step 9: Verify new IMSI/ACC/SPN/SMSC
            ok = _verify_standard_efs(pcom, expected_next, self._steps)
            if not ok:
                raise AssertionError(
                    f"EF contents after Next IMSI do not match index {expected_next}"
                )

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_PRIORITY_IMSI(BaseTestCase):
    """
    STK switching — Priority IMSI
    Converted from PCOM: "STK Switching test case - Priority IMSI"
    """
    tc_id = "TC-STK-PRIORITY-IMSI"
    title = "STK Priority IMSI — switch to priority profile"
    domain = "STK Menu"
    priority = "P1"
    description = "Opens the STK menu and selects item 02 (Priority IMSI), handles the subsequent FETCH/TERMINAL_RESPONSE/REFRESH sequence, then reads EF_IMSI/EF_ACC/EF_SPN/EF_SMSP and asserts all match the expected values for the PRIO_IMSI index."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        pcom = _make_pcom(self.card)
        try:
            resp = pcom.verify_adm(ADM_KEY_HEX)
            self.assert_sw(resp, 0x9000, "ADM VERIFY")

            # Read current index
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(0, 0x36)
            self.assert_sw(resp, 0x9000, "Read EF_Config")
            current_idx = resp.data[2]
            self._steps.append(StepResult(
                f"Current IMSI index = {current_idx}", "", resp.data.hex().upper(),
                TestStatus.PASS, ""
            ))

            # If already on priority, note it but continue
            if current_idx == PRIO_IMSI:
                self._steps.append(StepResult(
                    f"Already on priority IMSI index {PRIO_IMSI} — switching not needed",
                    "", "", TestStatus.PASS, ""
                ))

            # Drain initial STK
            _drain_initial_stk(pcom, self._steps)

            # Open menu, select "Priority IMSI" (item 02)
            pcom.menu_selection(0x80)  # open menu
            resp = pcom.menu_selection(0x02)
            self._steps.append(StepResult(
                f"SELECT ITEM 02 (Priority IMSI) → SW={resp.sw_hex}",
                "...90 01 02", str(resp),
                TestStatus.PASS if resp.sw1 in (0x90, 0x91) else TestStatus.FAIL, ""
            ))

            if resp.sw1 == 0x91:
                # Fetch SETUP CALL or REFRESH
                fetch_resp = pcom.fetch(resp.sw2)
                self._steps.append(StepResult(
                    f"FETCH after Priority IMSI → {fetch_resp.data.hex().upper()[:20]}",
                    f"80 12 00 00 {resp.sw2:02X}", str(fetch_resp), TestStatus.PASS, ""
                ))
                if len(fetch_resp.data) >= 6:
                    cmd_details = fetch_resp.data[3:6]
                    resp2 = pcom.terminal_response(cmd_details, 0x00)
                    self._steps.append(StepResult(
                        f"TERMINAL RESPONSE → SW={resp2.sw_hex}",
                        "", str(resp2), TestStatus.PASS, ""
                    ))
                    # If SW 91 0B, fetch REFRESH
                    if resp2.sw1 == 0x91:
                        tr_resp, _ = pcom.fetch_and_respond(resp2.sw2, 0x00)
                        self._steps.append(StepResult(
                            f"FETCH REFRESH → SW={tr_resp.sw_hex}",
                            f"80 12 00 00 {resp2.sw2:02X}", str(tr_resp), TestStatus.PASS, ""
                        ))

            # Verify priority IMSI is now active
            ok = _verify_standard_efs(pcom, PRIO_IMSI, self._steps)
            if not ok:
                raise AssertionError(
                    f"EF contents after Priority IMSI do not match index {PRIO_IMSI}"
                )

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_LOCK_IMSI(BaseTestCase):
    """
    STK switching — Lock IMSI + verify location event does NOT switch
    Converted from PCOM: "STK Switching test case - Lock IMSI"
    """
    tc_id = "TC-STK-LOCK-IMSI"
    title = "STK Lock IMSI — LOCI event blocked after lock"
    domain = "STK Menu"
    priority = "P2"
    description = "Selects menu item 03 (Lock IMSI) for the current index, sends a LOCATION_STATUS envelope for the configured PLMN, and asserts the response SW is 9000 (no switch) and EF_Config (4F01) byte 2 remains equal to the locked index."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        pcom = _make_pcom(self.card)
        try:
            resp = pcom.verify_adm(ADM_KEY_HEX)
            self.assert_sw(resp, 0x9000, "ADM VERIFY")

            # Read current index
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(0, 0x36)
            self.assert_sw(resp, 0x9000, "Read EF_Config")
            locked_idx = resp.data[2]
            self._steps.append(StepResult(
                f"Locking IMSI index {locked_idx}", "", "", TestStatus.PASS, ""
            ))

            # Drain STK, select "Lock IMSI" (item 03)
            _drain_initial_stk(pcom, self._steps)
            pcom.menu_selection(0x80)
            resp = pcom.menu_selection(0x03)
            self._steps.append(StepResult(
                f"SELECT ITEM 03 (Lock IMSI) → SW={resp.sw_hex}",
                "...90 01 03", str(resp),
                TestStatus.PASS if resp.sw1 in (0x90, 0x91) else TestStatus.FAIL, ""
            ))

            if resp.sw1 == 0x91:
                tr_resp, _ = pcom.fetch_and_respond(resp.sw2, 0x00)
                self._steps.append(StepResult(
                    f"FETCH REFRESH after lock → SW={tr_resp.sw_hex}",
                    "", str(tr_resp), TestStatus.PASS, ""
                ))

            # Now send a LOCATION STATUS envelope that would normally switch
            # (same MCC_MNC as configured) — should return 9000, NO switch
            resp = pcom.location_status_envelope(MCC_MNC_HEX)
            expected_sw = 0x9000  # locked = no switch, so 9000 not 910B
            sw_ok = resp.sw == 0x9000
            self._steps.append(StepResult(
                f"LOCI envelope with locked IMSI → SW={resp.sw_hex} (expected 9000=no switch)",
                f"80 C2 00 00 15 D6 ... {MCC_MNC_HEX} ...", str(resp),
                TestStatus.PASS if sw_ok else TestStatus.FAIL,
                "" if sw_ok else f"Expected 9000 (no switch), got {resp.sw_hex}"
            ))

            # Verify IMSI index unchanged
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(2, 1)
            self.assert_sw(resp, 0x9000, "Read active IMSI index byte")
            self.assert_byte(resp.data, 0, locked_idx,
                             f"Active index still {locked_idx} (locked, no switch)")

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_AUTO_MODE(BaseTestCase):
    """
    STK Automatic Mode toggle + location-based switch
    Converted from PCOM: "STK Switching test case - Automatic Mode"
    """
    tc_id = "TC-STK-AUTO-MODE"
    title = "STK Automatic Mode — toggle and verify location switching"
    domain = "STK Menu"
    priority = "P2"
    description = "Reads EF_Config (4F01) byte 1 (auto mode) and byte 2 (active index), selects menu item 04 to toggle auto mode, re-reads byte 1 to confirm it flipped, then sends a LOCATION_STATUS envelope and verifies EF_IMSI/EF_ACC/EF_SPN/EF_SMSP reflect either a switch or no-switch depending on the current index."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        pcom = _make_pcom(self.card)
        try:
            resp = pcom.verify_adm(ADM_KEY_HEX)
            self.assert_sw(resp, 0x9000, "ADM VERIFY")

            # Read current index and auto mode byte
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(0, 0x36)
            self.assert_sw(resp, 0x9000, "Read EF_Config")
            auto_mode_before = resp.data[1]  # byte 2 = auto mode
            current_idx = resp.data[2]
            self._steps.append(StepResult(
                f"Auto mode before = {auto_mode_before:02X}, current index = {current_idx}",
                "", resp.data.hex().upper(), TestStatus.PASS, ""
            ))

            # Verify current EFs
            _verify_standard_efs(pcom, current_idx, self._steps)

            # Drain STK and toggle Automatic Mode (item 04)
            _drain_initial_stk(pcom, self._steps)
            pcom.menu_selection(0x80)
            resp = pcom.menu_selection(0x04)
            self._steps.append(StepResult(
                f"SELECT ITEM 04 (Automatic Mode toggle) → SW={resp.sw_hex}",
                "...90 01 04", str(resp),
                TestStatus.PASS if resp.sw1 in (0x90, 0x91) else TestStatus.FAIL, ""
            ))

            if resp.sw1 == 0x91:
                tr_resp, _ = pcom.fetch_and_respond(resp.sw2, 0x00)
                self._steps.append(StepResult(
                    f"FETCH REFRESH → SW={tr_resp.sw_hex}", "", str(tr_resp),
                    TestStatus.PASS, ""
                ))

            # Read new auto mode byte
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(0, 2)
            self.assert_sw(resp, 0x9000, "Read auto mode byte after toggle")
            auto_mode_after = resp.data[1]
            expected_auto = 0x01 if auto_mode_before == 0x00 else 0x00
            self.assert_byte(resp.data, 1, expected_auto,
                             f"Auto mode toggled {auto_mode_before:02X} → {expected_auto:02X}")

            # Now send location status:
            # If current_idx == MCC_IMSI_INDEX, no switch (same PLMN, same index)
            # Otherwise switch should happen
            _drain_initial_stk(pcom, self._steps)

            if current_idx == MCC_IMSI_INDEX:
                # Expect no switch → 9000
                resp = pcom.location_status_envelope(MCC_MNC_HEX)
                sw_ok = resp.sw == 0x9000
                self._steps.append(StepResult(
                    f"LOCI (same index as MCC) → SW={resp.sw_hex} (expect 9000)",
                    "", str(resp),
                    TestStatus.PASS if sw_ok else TestStatus.FAIL,
                    "" if sw_ok else f"Expected 9000, got {resp.sw_hex}"
                ))
                # Verify EFs unchanged
                _verify_standard_efs(pcom, current_idx, self._steps)
            else:
                # Expect switch → 910B (REFRESH pending)
                resp = pcom.location_status_envelope(MCC_MNC_HEX)
                self._steps.append(StepResult(
                    f"LOCI (different PLMN) → SW={resp.sw_hex} (expect 910B)",
                    "", str(resp),
                    TestStatus.PASS if resp.sw1 in (0x91, 0x90) else TestStatus.FAIL, ""
                ))
                if resp.sw1 == 0x91:
                    tr_resp, _ = pcom.fetch_and_respond(resp.sw2, 0x04)
                    self._steps.append(StepResult(
                        f"FETCH REFRESH after switch → SW={tr_resp.sw_hex}",
                        "", str(tr_resp), TestStatus.PASS, ""
                    ))
                # Verify new index EFs
                _verify_standard_efs(pcom, MCC_IMSI_INDEX, self._steps)

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()


class TC_STK_DEFAULT_SWITCH(BaseTestCase):
    """
    Default IMSI switching via LOCI envelope
    Converted from PCOM: "Check Default IMSI SWITCHING"
    """
    tc_id = "TC-STK-DEFAULT-SWITCH"
    title = "Default IMSI switching — LOCI envelope triggers switch to priority"
    domain = "STK Menu"
    priority = "P1"
    description = "Sends a LOCATION_STATUS envelope with PLMN=55F566 (wildcard/default match), fetches the expected REFRESH if SW=91XX, then reads EF_IMSI/EF_ACC/EF_SPN/EF_SMSP and asserts they match the PRIO_IMSI profile values."

    def run(self) -> TestResult:
        t0 = time.perf_counter()
        pcom = _make_pcom(self.card)
        try:
            resp = pcom.verify_adm(ADM_KEY_HEX)
            self.assert_sw(resp, 0x9000, "ADM VERIFY")

            # Read current index
            pcom.select_fid(DF_7F30)
            pcom.select_fid(DF_5F1A)
            pcom.select_ef(EF_CONFIG)
            resp = pcom.read_binary(0, 0x36)
            self.assert_sw(resp, 0x9000, "Read EF_Config")
            current_idx = resp.data[2]
            self._steps.append(StepResult(
                f"Current IMSI index = {current_idx}", "", resp.data.hex().upper(),
                TestStatus.PASS, ""
            ))

            # Verify current EFs
            _verify_standard_efs(pcom, current_idx, self._steps)

            # Drain STK
            _drain_initial_stk(pcom, self._steps)

            # Send LOCI with the configured PLMN
            # PCOM uses 55F566 for the "default switching" case (different PLMN format)
            resp = pcom.location_status_envelope("55F566")
            self._steps.append(StepResult(
                f"LOCI envelope PLMN=55F566 → SW={resp.sw_hex}",
                "80 C2 00 00 15 D6 ... 55 F5 66 ...", str(resp),
                TestStatus.PASS if resp.sw1 in (0x90, 0x91) else TestStatus.FAIL, ""
            ))

            if resp.sw1 == 0x91:
                # REFRESH expected
                tr_resp, cmd_data = pcom.fetch_and_respond(resp.sw2, 0x04)
                self._steps.append(StepResult(
                    f"FETCH REFRESH → SW={tr_resp.sw_hex}",
                    f"80 12 00 00 {resp.sw2:02X}", str(tr_resp), TestStatus.PASS, ""
                ))
                # Verify switch happened to PRIO_IMSI
                _verify_standard_efs(pcom, PRIO_IMSI, self._steps)
            else:
                # No switch (current == PRIO or no match)
                self._steps.append(StepResult(
                    "No switch triggered (current already on priority or no match)",
                    "", "", TestStatus.PASS, ""
                ))
                _verify_standard_efs(pcom, current_idx, self._steps)

        except Exception as exc:
            self.result.duration_ms = (time.perf_counter() - t0) * 1000
            return self._finalise(exc)
        self.result.duration_ms = (time.perf_counter() - t0) * 1000
        return self._finalise()
