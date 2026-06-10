from transport.connection import CardConnection
from engine.apdu import APDU, APDUResponse


class CardIO:
    """High-level file operations on top of raw APDU transport."""

    def __init__(self, conn: CardConnection):
        self._conn = conn

    def transmit(self, apdu: APDU) -> APDUResponse:
        data, sw1, sw2 = self._conn.transmit(apdu.to_list())
        return APDUResponse(bytes(data), sw1, sw2)

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
        apdu = APDU(0xA0, 0xC2, 0x00, 0x00, env_data)
        return self.transmit(apdu)

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
        """Read large files in chunks (handles >255 byte files)."""
        result = bytearray()
        offset = 0
        while offset < total_length:
            remaining = total_length - offset
            length = min(chunk_size, remaining)
            resp = self.read_binary(offset, length)
            if not resp.ok:
                break
            result.extend(resp.data)
            offset += len(resp.data)
        return bytes(result)

    def build_location_status_envelope(self, mcc: str, mnc: str,
                                        service_type: int) -> bytes:
        """
        Build DOWNLOAD_LOCATION_STATUS BER-TLV envelope.
        mcc: 3-digit string e.g. '404'
        mnc: 2 or 3-digit string e.g. '20' or '020'
        service_type: 0=Normal, 1=Limited, 2=No Service
        """
        # Encode PLMN per GSM 24.008: nibble-swapped MCC+MNC
        mcc_digits = mcc.zfill(3)
        mnc_digits = mnc.zfill(3) if len(mnc) == 3 else mnc.zfill(2) + 'F'

        plmn = bytes([
            int(mcc_digits[1]) << 4 | int(mcc_digits[0]),
            int(mnc_digits[0]) << 4 | int(mcc_digits[2]),
            int(mnc_digits[2]) << 4 | int(mnc_digits[1]),
        ])

        # Device identities TLV: 82 02 83 81 (network → UICC)
        dev_id = bytes([0x82, 0x02, 0x83, 0x81])
        # Location status TLV: 99 01 XX
        loc_status = bytes([0x99, 0x01, service_type])

        if service_type in (0, 1):
            # Location info TLV: 9B 06 [lac 2 bytes] [plmn 3 bytes] [cell 2 bytes]
            loc_info = bytes([0x9B, 0x06, 0x00, 0x00]) + plmn[:3] + bytes([0x00, 0x00])
            inner = dev_id + loc_status + loc_info
        else:
            inner = dev_id + loc_status

        # Event download: D6 tag
        envelope = bytes([0xD6, len(inner)]) + inner
        return envelope

    def send_location_status(self, mcc: str, mnc: str, service_type: int) -> APDUResponse:
        env = self.build_location_status_envelope(mcc, mnc, service_type)
        return self.send_envelope(env)

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
