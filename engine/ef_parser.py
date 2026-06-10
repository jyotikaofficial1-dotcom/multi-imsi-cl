"""EF (Elementary File) parser for common UICC/SIM elementary files."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Low-level BER-TLV helpers
# ---------------------------------------------------------------------------

def _decode_length(data: bytes, offset: int) -> tuple[int, int]:
    """Return (length_value, new_offset) from BER-TLV length encoding."""
    first = data[offset]
    offset += 1
    if first <= 0x7F:
        return first, offset
    n_bytes = first & 0x7F
    length = 0
    for _ in range(n_bytes):
        length = (length << 8) | data[offset]
        offset += 1
    return length, offset


def parse_tlv(data: bytes) -> list[tuple[int, bytes]]:
    """
    Parse flat BER-TLV data and return list of (tag, value) tuples.
    Only handles single-byte and two-byte tags.
    """
    result: list[tuple[int, bytes]] = []
    idx = 0
    while idx < len(data):
        if data[idx] == 0xFF or data[idx] == 0x00:
            idx += 1
            continue
        tag = data[idx]
        idx += 1
        if (tag & 0x1F) == 0x1F:  # two-byte tag
            tag = (tag << 8) | data[idx]
            idx += 1
        length, idx = _decode_length(data, idx)
        value = data[idx: idx + length]
        idx += length
        result.append((tag, value))
    return result


# ---------------------------------------------------------------------------
# EF-IMSI  (3GPP TS 31.102 §4.2.2)
# ---------------------------------------------------------------------------

def decode_imsi(ef_data: bytes) -> str:
    """
    Decode EF-IMSI binary content to an IMSI string.

    Byte 0 : length of IMSI content (n bytes).
    Byte 1 : bits[7:4] = first IMSI digit (or 0xF for filler),
             bit[3]   = parity (odd → 1).
    Bytes 2…n : two BCD digits per byte, lower nibble first.
    """
    if not ef_data:
        return ""
    length = ef_data[0]
    imsi_bytes = ef_data[1: 1 + length]

    digits: list[str] = []
    # First byte: upper nibble is first digit, skip parity bit[3]
    first = (imsi_bytes[0] >> 4) & 0x0F
    if first != 0x0F:
        digits.append(str(first))

    for byte in imsi_bytes[1:]:
        lo = byte & 0x0F
        hi = (byte >> 4) & 0x0F
        if lo != 0x0F:
            digits.append(str(lo))
        if hi != 0x0F:
            digits.append(str(hi))

    return "".join(digits)


def encode_imsi(imsi: str) -> bytes:
    """Encode an IMSI string into EF-IMSI binary format."""
    # Pad to even length
    padded = imsi + ("F" if len(imsi) % 2 == 0 else "")
    nibbles = [int(c, 16) if c != "F" else 0x0F for c in padded]

    imsi_bytes = bytearray()
    # First byte: parity (odd=1) in bit3, first digit in upper nibble
    first_byte = 0x09 | (nibbles[0] << 4)  # odd parity
    imsi_bytes.append(first_byte)

    for i in range(1, len(nibbles), 2):
        lo = nibbles[i]
        hi = nibbles[i + 1] if i + 1 < len(nibbles) else 0x0F
        imsi_bytes.append(lo | (hi << 4))

    return bytes([len(imsi_bytes)]) + bytes(imsi_bytes)


# ---------------------------------------------------------------------------
# EF-LOCI  (GSM 11.11 §10.3.4 / 3GPP TS 31.102 §4.2.10)
# ---------------------------------------------------------------------------

@dataclass
class LocationInfo:
    tmsi: bytes          # 4 bytes
    lai: bytes           # 5 bytes (MCC+MNC+LAC)
    tmsi_time: int       # 1 byte
    location_status: int # 1 byte (0=updated, 1=not updated, 2=PLMN not allowed)

    @property
    def mcc(self) -> str:
        b0, b1 = self.lai[0], self.lai[1]
        d1 = b0 & 0x0F
        d2 = (b0 >> 4) & 0x0F
        d3 = b1 & 0x0F
        return f"{d1}{d2}{d3}"

    @property
    def mnc(self) -> str:
        b1, b2 = self.lai[1], self.lai[2]
        d1 = (b1 >> 4) & 0x0F
        d2 = b2 & 0x0F
        d3 = (b2 >> 4) & 0x0F
        if d3 == 0x0F:
            return f"{d1}{d2}"
        return f"{d1}{d2}{d3}"

    @property
    def lac(self) -> int:
        return (self.lai[3] << 8) | self.lai[4]


def decode_loci(ef_data: bytes) -> LocationInfo:
    """Parse EF-LOCI (11 bytes)."""
    if len(ef_data) < 11:
        raise ValueError(f"EF-LOCI too short: {len(ef_data)} bytes")
    return LocationInfo(
        tmsi=ef_data[0:4],
        lai=ef_data[4:9],
        tmsi_time=ef_data[9],
        location_status=ef_data[10],
    )


# ---------------------------------------------------------------------------
# EF-AD  (3GPP TS 31.102 §4.2.18)
# ---------------------------------------------------------------------------

@dataclass
class AdminData:
    ms_operation_mode: int      # byte 0
    additional_info: bytes      # bytes 1..2 (optional)
    mnc_length: int             # byte 3 (3 = 3-digit MNC)


def decode_ad(ef_data: bytes) -> AdminData:
    """Parse EF-AD."""
    if not ef_data:
        raise ValueError("EF-AD is empty")
    mode = ef_data[0]
    additional = ef_data[1:3] if len(ef_data) >= 3 else b"\x00\x00"
    mnc_len = ef_data[3] if len(ef_data) >= 4 else 2
    return AdminData(
        ms_operation_mode=mode,
        additional_info=additional,
        mnc_length=mnc_len,
    )


# ---------------------------------------------------------------------------
# EF-SMSP  (3GPP TS 31.102 §4.2.27)
# ---------------------------------------------------------------------------

@dataclass
class SMSParams:
    alpha_id: bytes
    tp_destination_address: Optional[bytes]
    tp_sc_address: Optional[bytes]
    tp_pid: Optional[int]
    tp_dcs: Optional[int]
    tp_vp: Optional[int]
    raw: bytes


def decode_smsp(record: bytes) -> SMSParams:
    """Parse one EF-SMSP record (variable length)."""
    if len(record) < 28:
        return SMSParams(b"", None, None, None, None, None, record)

    # Last byte is parameter indicator
    indicator = record[-1]
    alpha_len = len(record) - 28
    alpha_id = record[:alpha_len]
    rest = record[alpha_len:]

    dest = rest[1:13] if not (indicator & 0x01) else None
    sc = rest[13:25] if not (indicator & 0x02) else None
    pid = rest[25] if not (indicator & 0x04) else None
    dcs = rest[26] if not (indicator & 0x08) else None
    vp = rest[27] if not (indicator & 0x10) else None

    return SMSParams(
        alpha_id=alpha_id,
        tp_destination_address=dest,
        tp_sc_address=sc,
        tp_pid=pid,
        tp_dcs=dcs,
        tp_vp=vp,
        raw=record,
    )


# ---------------------------------------------------------------------------
# EF-SPN  (3GPP TS 31.102 §4.2.12)
# ---------------------------------------------------------------------------

@dataclass
class ServiceProviderName:
    display_condition: int   # byte 0
    name: str                # GSM-7 or UCS-2 decoded name


def _decode_gsm7(data: bytes) -> str:
    GSM7 = (
        "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./"
        "0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿"
        "abcdefghijklmnopqrstuvwxyzäöñüà"
    )
    return "".join(GSM7[b & 0x7F] if (b & 0x7F) < len(GSM7) else "?" for b in data if b != 0xFF)


def decode_spn(ef_data: bytes) -> ServiceProviderName:
    """Parse EF-SPN."""
    if not ef_data:
        return ServiceProviderName(0, "")
    display = ef_data[0]
    name_bytes = ef_data[1:].rstrip(b"\xFF")

    if name_bytes and name_bytes[0] == 0x80:
        # UCS-2 with BOM
        try:
            name = name_bytes[1:].decode("utf-16-be", errors="replace").rstrip("￿")
        except Exception:
            name = name_bytes.hex()
    elif name_bytes and name_bytes[0] == 0x81:
        name = name_bytes[2:].hex()  # simplified: return hex for 0x81 encoding
    else:
        name = _decode_gsm7(name_bytes)

    return ServiceProviderName(display_condition=display, name=name)


# ---------------------------------------------------------------------------
# EF-PNN  (3GPP TS 31.102 §4.2.58) - PLMN Network Name
# ---------------------------------------------------------------------------

@dataclass
class PLMNNetworkName:
    full_name: str
    short_name: str


def _decode_nw_name_tlv(data: bytes) -> str:
    """Decode Network Name TLV value (tag 0x43 or 0x45)."""
    if not data:
        return ""
    coding = (data[0] >> 4) & 0x07
    spare_bits = data[0] & 0x07
    name_data = data[1:]
    if coding == 0:  # GSM-7
        text = _decode_gsm7(name_data)
        if spare_bits:
            text = text[: -(spare_bits // 7 + 1)] if spare_bits else text
        return text
    elif coding == 1:  # UCS-2
        try:
            return name_data.decode("utf-16-be", errors="replace")
        except Exception:
            return name_data.hex()
    return name_data.hex()


def decode_pnn_record(record: bytes) -> PLMNNetworkName:
    """Parse one EF-PNN record."""
    tlvs = parse_tlv(record)
    full = ""
    short = ""
    for tag, value in tlvs:
        if tag == 0x43:
            full = _decode_nw_name_tlv(value)
        elif tag == 0x45:
            short = _decode_nw_name_tlv(value)
    return PLMNNetworkName(full_name=full, short_name=short)


# ---------------------------------------------------------------------------
# EF-OPL  (3GPP TS 31.102 §4.2.59) - Operator PLMN List
# ---------------------------------------------------------------------------

@dataclass
class OPLRecord:
    plmn: bytes     # 3 bytes nibble-encoded
    lac_start: int
    lac_end: int
    pnn_index: int  # 1-based index into EF-PNN; 0 = use EF-SPN

    @property
    def mcc_mnc(self) -> str:
        b0, b1, b2 = self.plmn
        mcc = f"{b0 & 0xF}{(b0 >> 4) & 0xF}{b1 & 0xF}"
        mnc3 = (b1 >> 4) & 0xF
        mnc = f"{b2 & 0xF}{(b2 >> 4) & 0xF}"
        if mnc3 != 0xF:
            mnc += str(mnc3)
        return mcc + mnc


def decode_opl_record(record: bytes) -> OPLRecord:
    """Parse one 8-byte EF-OPL record."""
    if len(record) < 8:
        raise ValueError(f"OPL record too short: {len(record)}")
    plmn = record[0:3]
    lac_start = (record[3] << 8) | record[4]
    lac_end = (record[5] << 8) | record[6]
    pnn_index = record[7]
    return OPLRecord(plmn=plmn, lac_start=lac_start, lac_end=lac_end, pnn_index=pnn_index)


# ---------------------------------------------------------------------------
# EF-FPLMN  (3GPP TS 31.102 §4.2.16) - Forbidden PLMNs
# ---------------------------------------------------------------------------

def decode_fplmn(ef_data: bytes) -> list[str]:
    """Return list of forbidden PLMN strings from EF-FPLMN."""
    result = []
    for i in range(0, len(ef_data) - 2, 3):
        chunk = ef_data[i: i + 3]
        if chunk == b"\xFF\xFF\xFF":
            continue
        b0, b1, b2 = chunk
        mcc = f"{b0 & 0xF}{(b0 >> 4) & 0xF}{b1 & 0xF}"
        mnc3 = (b1 >> 4) & 0xF
        mnc = f"{b2 & 0xF}{(b2 >> 4) & 0xF}"
        if mnc3 != 0xF:
            mnc += str(mnc3)
        result.append(mcc + mnc)
    return result


# ---------------------------------------------------------------------------
# EF-PLMNwAcT / EF-OPLMNwAcT / EF-HPLMNwAcT  (3GPP TS 31.102 §4.2.5)
# ---------------------------------------------------------------------------

@dataclass
class PLMNEntry:
    mcc_mnc: str
    access_tech: int   # bitmask, e.g. 0x8000 = UTRAN, 0x0080 = E-UTRAN


def decode_plmn_with_act(ef_data: bytes) -> list[PLMNEntry]:
    """Parse EF-PLMNwAcT / OPLMNwAcT / HPLMNwAcT (5 bytes per entry)."""
    entries = []
    for i in range(0, len(ef_data) - 4, 5):
        chunk = ef_data[i: i + 5]
        if chunk[:3] == b"\xFF\xFF\xFF":
            continue
        b0, b1, b2, at0, at1 = chunk
        mcc = f"{b0 & 0xF}{(b0 >> 4) & 0xF}{b1 & 0xF}"
        mnc3 = (b1 >> 4) & 0xF
        mnc = f"{b2 & 0xF}{(b2 >> 4) & 0xF}"
        if mnc3 != 0xF:
            mnc += str(mnc3)
        act = (at0 << 8) | at1
        entries.append(PLMNEntry(mcc_mnc=mcc + mnc, access_tech=act))
    return entries


# ---------------------------------------------------------------------------
# EF-ACC  (3GPP TS 31.102 §4.2.15)
# ---------------------------------------------------------------------------

def decode_acc(ef_data: bytes) -> int:
    """Return the 16-bit Access Control Class bitmask."""
    if len(ef_data) < 2:
        return 0
    return (ef_data[0] << 8) | ef_data[1]


# ---------------------------------------------------------------------------
# EF-MSISDN  (3GPP TS 31.102 §4.2.26)
# ---------------------------------------------------------------------------

@dataclass
class MSISDN:
    alpha_id: str
    number: str
    ton_npi: int


def _decode_bcd_number(data: bytes) -> str:
    digits = []
    for byte in data:
        lo = byte & 0x0F
        hi = (byte >> 4) & 0x0F
        if lo != 0x0F:
            digits.append(str(lo))
        if hi != 0x0F:
            digits.append(str(hi))
    return "".join(digits)


def decode_msisdn_record(record: bytes) -> MSISDN:
    """Parse one EF-MSISDN record (variable length, fixed trailer 14 bytes)."""
    if len(record) < 14:
        return MSISDN("", "", 0)
    alpha_len = len(record) - 14
    alpha_bytes = record[:alpha_len].rstrip(b"\xFF")
    try:
        alpha = alpha_bytes.decode("latin-1")
    except Exception:
        alpha = alpha_bytes.hex()

    trailer = record[alpha_len:]
    npi_ton = trailer[1]
    number_bcd = trailer[2:12]
    number = _decode_bcd_number(number_bcd)

    return MSISDN(alpha_id=alpha, number=number, ton_npi=npi_ton)


# ---------------------------------------------------------------------------
# EF-SST  (3GPP TS 31.102 §4.2.8) - SIM Service Table
# ---------------------------------------------------------------------------

def decode_sst(ef_data: bytes) -> dict[int, bool]:
    """
    Return a dict mapping service number (1-based) to enabled status.
    In USIM SST: bit n set means service n is available.
    """
    services: dict[int, bool] = {}
    for byte_idx, byte in enumerate(ef_data):
        for bit in range(8):
            svc_num = byte_idx * 8 + bit + 1
            services[svc_num] = bool(byte & (1 << bit))
    return services


# ---------------------------------------------------------------------------
# Generic FCP (File Control Parameters) TLV parser  (ISO/IEC 7816-4)
# ---------------------------------------------------------------------------

@dataclass
class FCPInfo:
    file_size: int = 0
    total_file_size: int = 0
    file_descriptor: bytes = b""
    file_id: bytes = b""
    df_name: bytes = b""
    life_cycle_status: int = 0
    record_length: int = 0
    num_records: int = 0


def parse_fcp(fcp_data: bytes) -> FCPInfo:
    """Parse FCP template (tag 0x62) returned by SELECT."""
    info = FCPInfo()
    # Strip outer 62 tag if present
    if fcp_data and fcp_data[0] == 0x62:
        length, offset = _decode_length(fcp_data, 1)
        fcp_data = fcp_data[offset: offset + length]

    tlvs = parse_tlv(fcp_data)
    for tag, value in tlvs:
        if tag == 0x80:
            info.file_size = int.from_bytes(value, "big")
        elif tag == 0x81:
            info.total_file_size = int.from_bytes(value, "big")
        elif tag == 0x82:
            info.file_descriptor = value
            if len(value) >= 5:
                info.record_length = (value[3] << 8) | value[4]
            if len(value) >= 6:
                info.num_records = value[5]
        elif tag == 0x83:
            info.file_id = value
        elif tag == 0x84:
            info.df_name = value
        elif tag == 0x8A:
            info.life_cycle_status = value[0] if value else 0
    return info
