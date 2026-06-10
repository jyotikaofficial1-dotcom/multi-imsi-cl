"""
PCOM-compatible card access helpers.
Adds step-by-step DF navigation and T=0 GET_RESPONSE chaining.
"""
from engine.apdu import APDU, APDUResponse
from transport.connection import CardConnection


class PcomCardIO:
    """
    Mirrors the PCOM script's exact APDU sequences:
      - SELECT with P1=00 P2=04 (returns FCP, 61XX on T=0)
      - Automatic GET_RESPONSE chaining
      - Step-by-step DF navigation (7F30 → 5F1A → EF)
    """

    def __init__(self, conn: CardConnection):
        self._conn = conn

    def _raw(self, apdu_list: list[int]) -> APDUResponse:
        data, sw1, sw2 = self._conn.transmit(apdu_list)
        resp = APDUResponse(bytes(data), sw1, sw2)
        # Auto-chain GET_RESPONSE for T=0 (61 XX)
        if sw1 == 0x61:
            gr = APDU(0x00, 0xC0, 0x00, 0x00, le=sw2)
            data2, sw1b, sw2b = self._conn.transmit(gr.to_list())
            resp = APDUResponse(bytes(data2), sw1b, sw2b)
        return resp

    def select_fid(self, fid_hex: str) -> APDUResponse:
        """SELECT by file ID (P1=00, P2=04) — matches PCOM 00 A4 00 04 02 XXXX."""
        fid = bytes.fromhex(fid_hex)
        return self._raw([0x00, 0xA4, 0x00, 0x04, len(fid)] + list(fid))

    def select_mf(self) -> APDUResponse:
        return self.select_fid("3F00")

    def nav_multi_imsi(self) -> APDUResponse:
        """Navigate to DF Multi-IMSI: SELECT 7F30 then SELECT 5F1A."""
        self.select_fid("7F30")
        return self.select_fid("5F1A")

    def nav_df_gsm(self) -> APDUResponse:
        """Navigate to DF GSM (7F20): SELECT 3F00 then SELECT 7F20."""
        self.select_mf()
        return self.select_fid("7F20")

    def nav_df_telecom(self) -> APDUResponse:
        """Navigate to DF Telecom (7F10)."""
        self.select_mf()
        return self.select_fid("7F10")

    def select_ef(self, ef_id: str) -> APDUResponse:
        """SELECT EF under current DF (P1=00, P2=04)."""
        return self.select_fid(ef_id)

    def read_binary(self, offset: int, length: int) -> APDUResponse:
        p1 = (offset >> 8) & 0x7F
        p2 = offset & 0xFF
        return self._raw([0x00, 0xB0, p1, p2, length])

    def read_record(self, rec_num: int, length: int) -> APDUResponse:
        """READ RECORD absolute (P2=04)."""
        return self._raw([0x00, 0xB2, rec_num, 0x04, length])

    def update_binary(self, offset: int, data: bytes) -> APDUResponse:
        p1 = (offset >> 8) & 0x7F
        p2 = offset & 0xFF
        return self._raw([0x00, 0xD6, p1, p2, len(data)] + list(data))

    def verify_adm(self, adm_hex: str) -> APDUResponse:
        """VERIFY ADM key: 00 20 00 0A 08 <key>."""
        key = bytes.fromhex(adm_hex)
        return self._raw([0x00, 0x20, 0x00, 0x0A, len(key)] + list(key))

    def terminal_profile(self) -> APDUResponse:
        """Send TERMINAL PROFILE (12 × FF)."""
        profile = [0xFF] * 12
        return self._raw([0x80, 0x10, 0x00, 0x00, 12] + profile)

    def fetch(self, length: int) -> APDUResponse:
        """FETCH proactive command (80 12 00 00 length)."""
        return self._raw([0x80, 0x12, 0x00, 0x00, length])

    def terminal_response(self, cmd_details: bytes, result: int = 0x00) -> APDUResponse:
        """
        Send TERMINAL RESPONSE for a proactive command.
        cmd_details: 3 bytes from the proactive command header (command number, type, qualifier)
        result: result code (0x00=OK, 0x04=success, icon not displayed)
        """
        # BER-TLV structure:
        # 81 03 [cmd_details]        - Command details
        # 02 02 82 81                - Device identities (keypad→UICC)
        # 03 01 [result]             - Result
        body = (
            bytes([0x81, 0x03]) + cmd_details +
            bytes([0x02, 0x02, 0x82, 0x81]) +
            bytes([0x03, 0x01, result])
        )
        return self._raw([0x80, 0x14, 0x00, 0x00, len(body)] + list(body))

    def handle_stk_loop(self, max_iter: int = 100) -> list[APDUResponse]:
        """
        Run the STK fetch/response loop until no more proactive commands.
        Returns list of all fetched proactive command responses.
        """
        fetched = []
        for _ in range(max_iter):
            tp_resp = self.terminal_profile()
            # After terminal profile, sw1=91 means proactive cmd pending
            sw1, sw2 = tp_resp.sw1, tp_resp.sw2
            if sw1 != 0x91:
                break
            fetch_resp = self.fetch(sw2)
            fetched.append(fetch_resp)
            if not fetch_resp.data or len(fetch_resp.data) < 6:
                break
            # Extract command details (bytes 3-5, 0-indexed)
            cmd_details = fetch_resp.data[3:6]
            self.terminal_response(cmd_details, 0x00)
            break  # Only handle first pending command
        return fetched

    def drain_stk(self, max_iter: int = 100) -> list[bytes]:
        """
        After terminal profile, drain all pending STK commands with OK responses.
        Returns list of proactive command TLVs fetched.
        """
        commands = []
        # Re-send terminal profile to get initial status
        resp = self.terminal_profile()
        for _ in range(max_iter):
            if resp.sw1 != 0x91:
                break
            fetch_resp = self.fetch(resp.sw2)
            commands.append(fetch_resp.data)
            if len(fetch_resp.data) >= 6:
                cmd_details = fetch_resp.data[3:6]
                resp = self.terminal_response(cmd_details, 0x00)
            else:
                break
        return commands

    def send_envelope(self, data: bytes) -> APDUResponse:
        """Send ENVELOPE (80 C2 00 00 len data)."""
        return self._raw([0x80, 0xC2, 0x00, 0x00, len(data)] + list(data))

    def menu_selection(self, item_id: int) -> APDUResponse:
        """
        ENVELOPE MENU SELECTION — matches PCOM:
        80C2000009 D3 07 82 02 01 81 90 01 [item_id]
        """
        envelope = bytes([0xD3, 0x07, 0x82, 0x02, 0x01, 0x81, 0x90, 0x01, item_id])
        return self.send_envelope(envelope)

    def location_status_envelope(self, plmn_hex: str, lac: str = "2A32",
                                  cell: str = "1234") -> APDUResponse:
        """
        ENVELOPE DOWNLOAD LOCATION STATUS — matches PCOM:
        80 C2 00 00 15  D6 13 19 01 03 02 02 82 81 1B 01 00 13 07 [PLMN] [LAC] [CELL]
        """
        plmn = bytes.fromhex(plmn_hex)
        lac_b = bytes.fromhex(lac)
        cell_b = bytes.fromhex(cell)
        inner = bytes([
            0x19, 0x01, 0x03,        # Event list: location status
            0x02, 0x02, 0x82, 0x81,  # Device identities
            0x1B, 0x01, 0x00,        # Location status: normal
            0x13, 0x07,              # Location info tag + length
        ]) + plmn + lac_b + cell_b
        envelope = bytes([0xD6, len(inner)]) + inner
        return self.send_envelope(envelope)

    def fetch_and_respond(self, length: int, result: int = 0x00) -> tuple[APDUResponse, bytes]:
        """FETCH a proactive command and immediately send TERMINAL RESPONSE."""
        fetch_resp = self.fetch(length)
        cmd_details = fetch_resp.data[3:6] if len(fetch_resp.data) >= 6 else bytes(3)
        tr_resp = self.terminal_response(cmd_details, result)
        return tr_resp, fetch_resp.data
