from transport.connection import CardConnection
from engine.apdu import APDU, APDUResponse


class CardIO:
    """High-level file operations on top of raw APDU transport."""

    def __init__(self, conn: CardConnection):
        self._conn = conn
        self._apdu_log: list[tuple[str, str]] = []  # [(tx_hex, rx_hex), ...]

    def transmit(self, apdu: APDU) -> APDUResponse:
        tx_hex = " ".join(f"{b:02X}" for b in apdu.to_list())
        data, sw1, sw2 = self._conn.transmit(apdu.to_list())
        resp = APDUResponse(bytes(data), sw1, sw2)
        rx_hex = (resp.data.hex().upper() + " " if resp.data else "") + resp.sw_hex
        self._apdu_log.append((tx_hex, rx_hex))
        return resp

    def get_apdu_log(self) -> list[tuple[str, str]]:
        return list(self._apdu_log)

    def clear_apdu_log(self) -> None:
        self._apdu_log.clear()

    def select_by_path(self, path_hex: str) -> APDUResponse:
        path = bytes.fromhex(path_hex)
        apdu = APDU(0x00, 0xA4, 0x08, 0x0C, path)
        return self.transmit(apdu)

    def select_by_id(self, fid_hex: str) -> APDUResponse:
        fid = bytes.fromhex(fid_hex)
        apdu = APDU(0x00, 0xA4, 0x00, 0x0C, fid)
        return self.transmit(apdu)

    def select_by_aid(self, aid_hex: str) -> APDUResponse:
        aid = bytes.fromhex(aid_hex)
        apdu = APDU(0x00, 0xA4, 0x04, 0x0C, aid)
        return self.transmit(apdu)

    def select_mf(self) -> APDUResponse:
        apdu = APDU(0x00, 0xA4, 0x00, 0x0C, bytes.fromhex("3F00"))
        return self.transmit(apdu)

    def read_binary(self, offset: int, length: int) -> APDUResponse:
        p1 = (offset >> 8) & 0x7F
        p2 = offset & 0xFF
        apdu = APDU(0x00, 0xB0, p1, p2, le=length)
        return self.transmit(apdu)

    def update_binary(self, offset: int, data: bytes) -> APDUResponse:
        p1 = (offset >> 8) & 0x7F
        p2 = offset & 0xFF
        apdu = APDU(0x00, 0xD6, p1, p2, data)
        return self.transmit(apdu)

    def read_record(self, rec_num: int, length: int) -> APDUResponse:
        apdu = APDU(0x00, 0xB2, rec_num, 0x04, le=length)
        return self.transmit(apdu)

    def send_envelope(self, env_data: bytes) -> APDUResponse:
        """ENVELOPE — CLA=80 per ETSI TS 102 221 §11.1.40."""
        apdu = APDU(0x80, 0xC2, 0x00, 0x00, env_data)
        return self.transmit(apdu)

    def terminal_profile(self) -> APDUResponse:
        """Send TERMINAL PROFILE (80 10 00 00 0C FF×12)."""
        profile = bytes([0xFF] * 12)
        apdu = APDU(0x80, 0x10, 0x00, 0x00, profile)
        return self.transmit(apdu)

    def _fetch(self, length: int) -> APDUResponse:
        """FETCH proactive command: 80 12 00 00 [len]."""
        apdu = APDU(0x80, 0x12, 0x00, 0x00, le=length)
        return self.transmit(apdu)

    def _terminal_response(self, cmd_type: int) -> APDUResponse:
        """TERMINAL RESPONSE OK for a fetched proactive command.
        Structure: cmd_details(01 03 01 [type] 00) + dev_ids(02 02 82 81) + result(03 01 00)
        """
        tr_data = bytes([
            0x01, 0x03, 0x01, cmd_type, 0x00,  # Command details
            0x02, 0x02, 0x82, 0x81,             # Device identities (keypad→UICC)
            0x03, 0x01, 0x00,                    # Result: OK
        ])
        apdu = APDU(0x80, 0x14, 0x00, 0x00, tr_data)
        return self.transmit(apdu)

    def run_proactive_session(self, max_iter: int = 100) -> list[str]:
        """Send TERMINAL PROFILE then drain any pending proactive commands.

        Loop (up to max_iter):
          - If SW1=0x91: FETCH(SW2) → TERMINAL RESPONSE → repeat
          - Otherwise: done

        Returns a list of human-readable log lines describing what happened.
        """
        log: list[str] = []

        resp = self.terminal_profile()
        log.append(f"TERMINAL PROFILE → SW={resp.sw_hex}")

        for _ in range(max_iter):
            if resp.sw1 != 0x91:
                break
            fetch_len = resp.sw2
            fetch_resp = self._fetch(fetch_len)
            log.append(f"  FETCH({fetch_len}) → {fetch_resp.data.hex().upper() or '(empty)'} SW={fetch_resp.sw_hex}")

            # Extract command type from fetch data byte index 5 (0-based)
            # Proactive cmd structure: D0 [len] 81 03 [num] [type] [qual] ...
            cmd_type = fetch_resp.data[5] if len(fetch_resp.data) > 5 else 0x00
            tr_resp = self._terminal_response(cmd_type)
            log.append(f"  TERMINAL RESPONSE(type={cmd_type:02X}) → SW={tr_resp.sw_hex}")
            resp = tr_resp

        log.append("Proactive session complete.")
        return log

    def send_status(self) -> APDUResponse:
        apdu = APDU(0x00, 0xF2, 0x00, 0x00, le=0)
        return self.transmit(apdu)

    def read_ef(self, df_path: str, ef_id: str,
                offset: int = 0, length: int = 0) -> tuple[bytes, APDUResponse]:
        self.select_by_path(df_path)
        self.select_by_id(ef_id)
        resp = self.read_binary(offset, length)
        return resp.data, resp

    def read_binary_chunked(self, total_length: int, chunk_size: int = 0xEF) -> bytes:
        """Read large files in chunks (handles >255 byte files).

        Accepts SW=9000 and SW=6282 (End-of-File warning — data still returned).
        Stops on any other SW or when the card returns fewer bytes than requested.
        """
        result = bytearray()
        offset = 0
        while offset < total_length:
            remaining = total_length - offset
            length = min(chunk_size, remaining)
            resp = self.read_binary(offset, length)
            if resp.ok or resp.sw == 0x6282:
                if resp.data:
                    result.extend(resp.data)
                if resp.sw == 0x6282 or len(resp.data) < length:
                    break   # reached end of file
                offset += len(resp.data)
            else:
                break
        return bytes(result)

    def build_location_status_envelope(self, mcc: str, mnc: str,
                                        service_type: int) -> bytes:
        """Build DOWNLOAD_LOCATION_STATUS BER-TLV envelope.
        mcc: 3-digit string e.g. '204'
        mnc: 2 or 3-digit string e.g. '66' or '066'
        service_type: 0=Normal, 1=Limited, 2=No Service
        """
        mcc = mcc.zfill(3)
        mnc3 = mnc.zfill(3) if len(mnc) == 3 else mnc.zfill(2) + 'F'

        def nib(c: str) -> int:
            return 0xF if c.upper() == 'F' else int(c)

        # PLMN encoding per GSM 04.08:
        # Byte 0: MCC[1] (high nibble) | MCC[0] (low nibble)
        # Byte 1: MNC[2] (high nibble) | MCC[2] (low nibble)
        # Byte 2: MNC[1] (high nibble) | MNC[0] (low nibble)
        plmn = bytes([
            (nib(mcc[1]) << 4) | nib(mcc[0]),
            (nib(mnc3[2]) << 4) | nib(mcc[2]),
            (nib(mnc3[1]) << 4) | nib(mnc3[0]),
        ])

        dev_id     = bytes([0x82, 0x02, 0x83, 0x81])  # network → UICC
        loc_status = bytes([0x99, 0x01, service_type])

        if service_type in (0, 1):
            loc_info = bytes([0x9B, 0x06, 0x00, 0x00]) + plmn + bytes([0x00, 0x00])
            inner = dev_id + loc_status + loc_info
        else:
            inner = dev_id + loc_status

        return bytes([0xD6, len(inner)]) + inner

    def send_location_status(self, mcc: str, mnc: str, service_type: int) -> APDUResponse:
        env = self.build_location_status_envelope(mcc, mnc, service_type)
        return self.send_envelope(env)

    def read_ef_dir(self) -> dict[str, str]:
        """Read EF DIR (2F00) under MF and return discovered AIDs.

        Returns dict with keys like 'USIM', 'ISIM', 'OTHER' mapping to AID hex strings.
        Parses Application Template (tag 61) TLVs; inner tag 4F = AID, 50 = label.
        """
        aids: dict[str, str] = {}
        try:
            self.select_mf()
            fid = bytes.fromhex("2F00")
            apdu = APDU(0x00, 0xA4, 0x00, 0x04, fid)  # select with response
            resp = self.transmit(apdu)
            # Read up to 256 bytes of EF DIR
            data = self.read_binary_chunked(256)
            i = 0
            while i < len(data):
                if data[i] != 0x61:
                    i += 1
                    continue
                if i + 1 >= len(data):
                    break
                tlen = data[i + 1]
                inner = data[i + 2: i + 2 + tlen]
                i += 2 + tlen
                # Parse inner TLVs
                aid = b""
                label = ""
                j = 0
                while j < len(inner):
                    tag = inner[j]
                    if j + 1 >= len(inner):
                        break
                    vlen = inner[j + 1]
                    val = inner[j + 2: j + 2 + vlen]
                    j += 2 + vlen
                    if tag == 0x4F:
                        aid = val
                    elif tag == 0x50:
                        try:
                            label = val.decode("ascii", errors="replace")
                        except Exception:
                            label = val.hex()
                if not aid:
                    continue
                aid_hex = aid.hex().upper()
                # Classify by RID / label
                upper_label = label.upper()
                if "USIM" in upper_label or aid_hex.startswith("A0000000871002"):
                    aids["USIM"] = aid_hex
                elif "ISIM" in upper_label or aid_hex.startswith("A0000000871004"):
                    aids["ISIM"] = aid_hex
                else:
                    aids.setdefault("OTHER", aid_hex)
        except Exception:
            pass
        return aids

    def verify_adm(self, adm_key_hex: str) -> APDUResponse:
        """Verify ADM key: 00 20 00 0A 08 <8-byte key>."""
        key = bytes.fromhex(adm_key_hex)
        apdu = APDU(0x00, 0x20, 0x00, 0x0A, key)
        return self.transmit(apdu)

    def send_menu_selection(self, item_id: int, help_request: bool = False) -> APDUResponse:
        """Send ENVELOPE MENU SELECTION for STK menu item."""
        # Device identities: 82 02 01 82 (keypad → card)
        dev_id = bytes([0x82, 0x02, 0x01, 0x82])
        # Item identifier: 90 01 XX
        item = bytes([0x90, 0x01, item_id])
        # Help request: 91 01 00
        help_tlv = bytes([0x91, 0x01, 0x01 if help_request else 0x00])
        inner = dev_id + item + help_tlv
        envelope = bytes([0xD3, len(inner)]) + inner
        return self.send_envelope(envelope)
