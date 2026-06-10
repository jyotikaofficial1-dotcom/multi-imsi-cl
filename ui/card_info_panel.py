"""
Card Information Panel — reads and displays parsed content of all
Multi-IMSI proprietary files (DF 7F30/5F1A) on card connect or on demand.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTextEdit, QSizePolicy, QProgressBar, QListWidget,
    QListWidgetItem
)

from engine.mcc_lookup import country_for_mcc


# ── file IDs ─────────────────────────────────────────────────────────────────
DF_MULTI     = "7F305F1A"
EF_CONFIG    = "4F01"
EF_MCC_LIST  = "4F03"
EF_IMSI_LIST = "4F07"

OTHER_FILES = [
    ("4F0C", "SPN List",         "3 profiles × 17 bytes"),
    ("4F42", "SMSP List",        "3 profiles × 43 bytes"),
    ("4F62", "HPLMNwAcT List",   "3 profiles × EF size"),
    ("4F78", "ACC List",         "3 profiles × 2 bytes"),
    ("4F7B", "FPLMN List",       "3 profiles × 12 bytes"),
    ("007B", "FPLMN ADF List",   "3 profiles × EF size"),
    ("4F32", "IMPI List",        "optional (ISIM)"),
    ("4F33", "DOMAIN List",      "optional (ISIM)"),
    ("4F34", "IMPU List",        "optional (ISIM)"),
    ("4F57", "SUCI Calc Info",   "optional (5G)"),
    ("4F58", "OPL5G List",       "optional (5G)"),
]

# ── ETSI / GSM parsing helpers ───────────────────────────────────────────────

_WILD = 0xD  # proprietary wildcard nibble value in 4F03

def _nib(v: int) -> str:
    if v == _WILD: return "D"
    if v == 0xF:   return "F"
    return str(v)


def _decode_plmn_bytes(b: bytes) -> tuple[str, str, bool]:
    """
    Decode 3-byte GSM 04.08 PLMN → (mcc_str, mnc_str, is_wildcard).
    Byte layout:
      b[0] = MCC[1]<<4 | MCC[0]
      b[1] = MNC[3]<<4 | MCC[2]   (MNC[3]=0xF → 2-digit MNC)
      b[2] = MNC[2]<<4 | MNC[1]   (digit ordering: MNC = MNC[1]MNC[2]MNC[3])
    Wait — standard per TS 24.008 §10.5.1.13:
      b[0] bits 3-0 = MCC digit 1, bits 7-4 = MCC digit 2
      b[1] bits 3-0 = MCC digit 3, bits 7-4 = MNC digit 3 (0xF=filler)
      b[2] bits 3-0 = MNC digit 1, bits 7-4 = MNC digit 2
    """
    mcc_d1 = b[0] & 0xF
    mcc_d2 = (b[0] >> 4) & 0xF
    mcc_d3 = b[1] & 0xF
    mnc_d3 = (b[1] >> 4) & 0xF   # 0xF = 2-digit MNC filler
    mnc_d1 = b[2] & 0xF
    mnc_d2 = (b[2] >> 4) & 0xF

    mcc = _nib(mcc_d1) + _nib(mcc_d2) + _nib(mcc_d3)

    if mnc_d3 == 0xF:             # 2-digit MNC
        mnc = _nib(mnc_d1) + _nib(mnc_d2)
    else:                         # 3-digit MNC
        mnc = _nib(mnc_d1) + _nib(mnc_d2) + _nib(mnc_d3)

    wildcard = (
        _WILD in (mcc_d1, mcc_d2, mcc_d3) or
        _WILD in (mnc_d1, mnc_d2, mnc_d3)
    )
    return mcc, mnc, wildcard


def _decode_imsi(b: bytes) -> str:
    """9-byte BCD IMSI: byte0=length, byte1 low nibble=parity(9), rest=digits."""
    if len(b) < 2:
        return "—"
    nibbles = []
    for byte in b[1:]:
        nibbles.append(byte & 0xF)
        nibbles.append((byte >> 4) & 0xF)
    digits = nibbles[1:]                # skip parity nibble
    while digits and digits[-1] == 0xF:
        digits.pop()
    return "".join(str(d) for d in digits) or "—"


def _decode_bcd_phone(bcd: bytes) -> str:
    """Convert BCD semi-octets to phone digit string (skip 0xF padding)."""
    digits = []
    for b in bcd:
        lo = b & 0xF
        hi = (b >> 4) & 0xF
        if lo != 0xF: digits.append(str(lo))
        if hi != 0xF: digits.append(str(hi))
    return "".join(digits)


def _decode_gsm7(b: bytes) -> str:
    """Best-effort decode of bytes as GSM-7 / Latin-1 string, strip 0xFF padding."""
    out = []
    for byte in b:
        if byte == 0xFF:
            break
        if 0x20 <= byte <= 0x7E:
            out.append(chr(byte))
        elif byte == 0x00:
            out.append(" ")
    return "".join(out).strip()


def _bool_str(b: int) -> str:
    return "Enabled" if b else "Disabled"


# ── EF_CONFIG (4F01) parser ──────────────────────────────────────────────────

def _parse_ef_config(data: bytes) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if not data:
        return [("Error", "—", "No data returned from card")]
    try:
        off = 0

        def rb(n: int = 1) -> bytes:
            nonlocal off
            v = data[off:off + n]
            off += n
            return v

        rows.append(("Applet Mode",        _bool_str(rb()[0]),   "0x01=enabled, 0x00=disabled"))
        rows.append(("Automatic Mode",     _bool_str(rb()[0]),   "Auto IMSI switching on location event"))
        rows.append(("Active IMSI Index",  str(rb()[0]),         "Currently active profile number"))
        rows.append(("Periodic Switching", _bool_str(rb()[0]),   "Periodic STATUS command check"))
        rows.append(("Periodic Counter",   str(rb()[0]),         "Number of STATUS commands between checks"))
        rows.append(("Max IMSI Profiles",  str(rb()[0]),         "Maximum supported profiles (≤10)"))
        rows.append(("Round Robin",        _bool_str(rb()[0]),   "Round-robin switching on network loss"))
        rb()  # RFU
        x = rb()[0]
        rows.append(("Menu Text Length",   str(x),               "Length of STK main menu label (bytes)"))
        menu_text = _decode_gsm7(rb(x)) if x else ""
        rows.append(("Menu Text",          menu_text or "—",     "STK main menu label"))
        rows.append(("Poll Interval",      f"{rb()[0]} s",        "STATUS polling interval (default 30s)"))
        rb(); rb(); rb()   # 3 × RFU
        rows.append(("Fallback Counter",   str(rb()[0]),         "STATUS count before fallback triggers"))
        rows.append(("Fallback Mode",      _bool_str(rb()[0]),   "Fallback mode flag"))
        rb()               # RFU
        rows.append(("Refresh Type",       f"0x{rb()[0]:02X}",   "REFRESH command qualifier"))
        rows.append(("Default LOCI Flag",  str(rb()[0]),         "Use received PLMN for LOCI initialisation"))
        y = rb()[0]
        rows.append(("PoR Config Length",  str(y),               "Length of PoR configuration data"))
        if y:
            rows.append(("PoR Config",     rb(y).hex().upper(),  "PoR record update specification"))
        u = rb()[0]
        rows.append(("ISIM AID Length",    str(u),               "0 = ISIM AID not present"))
        if 0x0A <= u <= 0x10:
            rows.append(("ISIM AID",       rb(u).hex().upper(),  "ADF ISIM application identifier"))
        elif u:
            rb(u)
        s = rb()[0]
        rows.append(("USIM AID Length",    str(s),               "0 = USIM AID not present"))
        if 0x0A <= s <= 0x10:
            rows.append(("USIM AID",       rb(s).hex().upper(),  "ADF USIM application identifier"))
    except (IndexError, Exception) as e:
        rows.append(("(parse stopped)",    str(e),               "Reached end of data"))
    return rows


# ── EF_MCC_LIST (4F03) parser ────────────────────────────────────────────────

def _parse_mcc_list(data: bytes) -> list[dict]:
    """
    Parse 4F03.  Each 4-byte entry: [PLMN 3B][IMSI_INDEX 1B].
    Skips 0xFF-padded entries.  Returns list of dicts.
    """
    entries = []
    i = 0
    n = 0
    while i + 3 < len(data):
        plmn = data[i:i + 3]
        idx  = data[i + 3]
        i += 4
        if plmn == b"\xFF\xFF\xFF":   # padding sentinel
            continue
        if all(b == 0xFF for b in [*plmn, idx]):
            continue
        # Skip entirely-zero entries (uninitialized)
        if plmn == b"\x00\x00\x00" and idx == 0:
            continue
        n += 1
        mcc, mnc, wild = _decode_plmn_bytes(plmn)
        # MCC digit 3 of 0xF means encoding error / non-standard entry
        mcc_d3 = plmn[1] & 0xF
        invalid_mcc = (mcc_d3 == 0xF and not wild)  # 'F' in MCC[2] pos
        country = "" if invalid_mcc else country_for_mcc(mcc)
        # Flag suspicious IMSI index (0xDD wildcard or out of normal range)
        idx_note = ""
        if idx == 0xDD:
            idx_note = " (wildcard)"
        elif idx == 0xFF:
            idx_note = " (unused)"
        entries.append(dict(
            num=n, plmn_hex=plmn.hex().upper(),
            mcc=mcc, mnc=mnc, wildcard=wild,
            country=country, idx=idx, idx_note=idx_note,
            invalid=invalid_mcc,
        ))
    return entries


# ── EF_IMSI_LIST (4F07) parser ───────────────────────────────────────────────

def _parse_imsi_list(data: bytes, max_profiles: int = 10) -> list[tuple[int, str, str]]:
    entries = []
    for i in range(max_profiles):
        off = i * 9
        if off + 9 > len(data):
            break
        slot = data[off:off + 9]
        if slot == b"\xFF" * 9 or slot == b"\x00" * 9:
            continue
        entries.append((i + 1, slot.hex().upper(), _decode_imsi(slot)))
    return entries


# ── SMSP (4F42) per-record ETSI parser ───────────────────────────────────────

def _parse_smsp_record(rec: bytes) -> dict:
    """
    Parse one SMSP record per ETSI TS 131.102 §4.2.25 / 3GPP TS 31.102.
    Record length L must be ≥ 28.  Fixed-length trailer = 27 bytes:
      byte L-27: TP-Parameter Indicator
      bytes L-26..L-17: TP-Destination Address (10 bytes)
      bytes L-16..L-7:  TP-SC Address (10 bytes)
      byte L-6:  TP-Protocol Identifier
      byte L-5:  TP-DCS
      bytes L-4..L-2: TP-Validity Period (3 bytes)
      byte L-1:  (sometimes padding; some implementations use 28-byte records)
    Alpha identifier = bytes 0..(L-28) if L>28 else empty.
    """
    L = len(rec)
    if L < 28:
        return {"error": f"Record too short ({L} bytes, need ≥28)"}

    alpha_len = L - 28
    alpha_raw = rec[:alpha_len] if alpha_len > 0 else b""
    alpha = _decode_gsm7(alpha_raw) if alpha_raw else ""

    tp_pi  = rec[L - 27]    # TP-Parameter Indicator bitmap
    tp_da  = rec[L - 26: L - 16]
    tp_sca = rec[L - 16: L - 6]
    tp_pid = rec[L - 6]
    tp_dcs = rec[L - 5]
    tp_vp  = rec[L - 4: L - 1]

    # Decode TP-SC Address (SMSC number)
    smsc = _decode_smsc_address(tp_sca)

    # TP-Parameter Indicator bits (see 3GPP TS 23.040 §9.2.3.27)
    pi_bits = {
        "TP-DA": bool(tp_pi & 0x01),
        "TP-SC": bool(tp_pi & 0x02),
        "TP-PID": bool(tp_pi & 0x04),
        "TP-DCS": bool(tp_pi & 0x08),
        "TP-VP": bool(tp_pi & 0x10),
    }

    return {
        "alpha": alpha or "—",
        "smsc": smsc,
        "tp_pi": f"0x{tp_pi:02X}",
        "pi_valid": pi_bits,
        "tp_pid": f"0x{tp_pid:02X}",
        "tp_dcs": f"0x{tp_dcs:02X}",
        "tp_vp": tp_vp.hex().upper(),
        "raw_sca": tp_sca.hex().upper(),
    }


def _decode_smsc_address(sca: bytes) -> str:
    """Decode 10-byte TP-SC Address field → '+XXXXXXX' or '—'."""
    if len(sca) < 2:
        return "—"
    num_bytes = sca[0]  # number of bytes that follow (including TON/NPI)
    if num_bytes == 0 or num_bytes == 0xFF:
        return "—"
    ton_npi = sca[1] if len(sca) > 1 else 0
    bcd_bytes = sca[2: 2 + max(0, num_bytes - 1)]
    number = _decode_bcd_phone(bcd_bytes)
    if not number:
        return "—"
    prefix = "+" if (ton_npi & 0x70) == 0x10 else ""  # 0x10 = international TON
    return prefix + number


def _parse_smsp_list(data: bytes, record_len: int = 43) -> list[dict]:
    """Split SMSP list into records and parse each."""
    if not data or record_len < 28:
        return []
    records = []
    for i in range(len(data) // record_len):
        rec = data[i * record_len: (i + 1) * record_len]
        if rec == b"\xFF" * record_len:
            continue
        parsed = _parse_smsp_record(rec)
        parsed["slot"] = i + 1
        records.append(parsed)
    return records


# ── SPN List (4F0C) parser ───────────────────────────────────────────────────

def _parse_spn_list(data: bytes, entry_len: int = 17) -> list[tuple[int, str, str]]:
    """
    Each SPN entry: byte 0 = display condition, bytes 1-16 = name.
    Display condition bits:
      bit 0 = show PLMN name when registered on HPLMN or EHPLMN
      bit 1 = show SPN when roaming
    """
    entries = []
    for i in range(len(data) // entry_len):
        off = i * entry_len
        entry = data[off: off + entry_len]
        if entry == b"\xFF" * entry_len:
            continue
        disp = entry[0]
        name_raw = entry[1:entry_len]
        # Check for UCS2 (starts with 0x80 or 0x81 or 0x82)
        if name_raw[0] in (0x80, 0x81, 0x82):
            try:
                if name_raw[0] == 0x80:
                    name = name_raw[1:].decode("utf-16-be", errors="replace").rstrip("\xFF").strip()
                else:
                    name = _decode_gsm7(name_raw[1:])
            except Exception:
                name = _decode_gsm7(name_raw)
        else:
            name = _decode_gsm7(name_raw)
        cond_parts = []
        if disp & 0x01: cond_parts.append("hide on HPLMN")
        if disp & 0x02: cond_parts.append("hide on roaming")
        cond = ", ".join(cond_parts) if cond_parts else "show always"
        entries.append((i + 1, name.strip() or "—", cond))
    return entries


# ── ACC List (4F78) parser ───────────────────────────────────────────────────

def _parse_acc_list(data: bytes, entry_len: int = 2) -> list[tuple[int, str, str]]:
    """
    Each ACC entry: 2 bytes = access class membership bitmask.
    Classes 0-9 are normal, 10-15 are special (operators/emergency).
    """
    entries = []
    for i in range(len(data) // entry_len):
        off = i * entry_len
        entry = data[off: off + entry_len]
        if entry == b"\xFF\xFF" or entry == b"\x00\x00":
            raw = int.from_bytes(entry, "big")
            classes = "—" if entry == b"\xFF\xFF" else "none"
            entries.append((i + 1, f"0x{raw:04X}", classes))
            continue
        raw = int.from_bytes(entry, "big")
        classes = ", ".join(str(b) for b in range(16) if raw & (1 << b))
        entries.append((i + 1, f"0x{raw:04X}", classes or "none"))
    return entries


# ── FPLMN List (4F7B) parser ─────────────────────────────────────────────────

def _parse_fplmn_list(data: bytes, entry_size: int = 12) -> list[tuple[int, list[str]]]:
    """Each FPLMN entry = 12 bytes = 4 × 3-byte PLMNs."""
    result = []
    for i in range(len(data) // entry_size):
        off = i * entry_size
        entry = data[off: off + entry_size]
        plmns = []
        for j in range(4):
            p = entry[j * 3: j * 3 + 3]
            if p == b"\xFF\xFF\xFF":
                continue
            mcc, mnc, _ = _decode_plmn_bytes(p)
            plmns.append(f"{mcc}/{mnc}")
        result.append((i + 1, plmns))
    return result


# ── background reader ─────────────────────────────────────────────────────────

class _Reader(QObject):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, card):
        super().__init__()
        self._card = card

    def run(self):
        results: dict[str, bytes | None] = {}
        try:
            c = self._card
            for fid, size in {EF_CONFIG: 64, EF_MCC_LIST: 500, EF_IMSI_LIST: 90}.items():
                try:
                    c.select_by_path(DF_MULTI)
                    resp = c.select_by_id(fid)
                    if not (resp.ok or resp.sw1 == 0x61):
                        results[fid] = None
                        continue
                    data = c.read_binary_chunked(size)
                    results[fid] = data or None
                except Exception:
                    results[fid] = None

            for fid, *_ in OTHER_FILES:
                try:
                    c.select_by_path(DF_MULTI)
                    resp = c.select_by_id(fid)
                    if not (resp.ok or resp.sw1 == 0x61):
                        results[fid] = None
                        continue
                    data = c.read_binary_chunked(512)
                    results[fid] = data or None
                except Exception:
                    results[fid] = None

        except Exception as e:
            self.error.emit(str(e))
            return
        self.done.emit(results)


# ── panel ─────────────────────────────────────────────────────────────────────

class CardInfoPanel(QWidget):
    """Displays parsed content of all DF Multi-IMSI files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._card = None
        self._thread: QThread | None = None
        self._reader: _Reader | None = None
        self._raw_results: dict = {}
        self._build_ui()

    def set_card(self, card) -> None:
        self._card = card
        if card:
            self._btn_refresh.setEnabled(True)
            self.refresh()
        else:
            self._btn_refresh.setEnabled(False)
            self._set_status("Not connected", "#888888")
            self._clear_all()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Card Personalisation Data")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._status_lbl = QLabel("Not connected")
        self._status_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(14)
        self._progress.setVisible(False)
        self._btn_refresh = QPushButton("🔄 Refresh")
        self._btn_refresh.setFixedWidth(100)
        self._btn_refresh.setEnabled(False)
        self._btn_refresh.clicked.connect(self.refresh)
        hdr.addWidget(title)
        hdr.addWidget(self._status_lbl, stretch=1)
        hdr.addWidget(self._progress)
        hdr.addWidget(self._btn_refresh)
        root.addLayout(hdr)

        # Sub-tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tab_config = self._make_kv_tab()
        self._tab_mcc    = self._make_mcc_tab()
        self._tab_imsi   = self._make_imsi_tab()
        self._tab_files  = self._make_files_tab()

        self._tabs.addTab(self._tab_config, "Config (4F01)")
        self._tabs.addTab(self._tab_mcc,    "MCC List (4F03)")
        self._tabs.addTab(self._tab_imsi,   "IMSI List (4F07)")
        self._tabs.addTab(self._tab_files,  "All Files")

        root.addWidget(self._tabs, stretch=1)

    # ── tab factories ─────────────────────────────────────────────────────────

    def _make_kv_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        tbl = QTableWidget(0, 3)
        tbl.setHorizontalHeaderLabels(["Field", "Value", "Description"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        _style_table(tbl)
        lay.addWidget(tbl)
        w._table = tbl
        return w

    def _make_mcc_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        info = QLabel(
            "PLMN encoding: GSM TS 24.008 §10.5.1.13 — 3 bytes, nibble-swapped BCD. "
            "Nibble 'D' = proprietary wildcard (matches any digit).  "
            "Nibble 'F' in MNC[3] position = 2-digit MNC filler."
        )
        info.setStyleSheet("color: #666; font-size: 11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # Summary label (entry count)
        self._mcc_count_lbl = QLabel("")
        self._mcc_count_lbl.setStyleSheet("font-size: 11px; color: #1565c0;")
        lay.addWidget(self._mcc_count_lbl)

        tbl = QTableWidget(0, 7)
        tbl.setHorizontalHeaderLabels(
            ["#", "PLMN (hex)", "MCC", "MNC", "Country", "Wildcard", "IMSI Index"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for col, mode in enumerate([
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
        ]):
            tbl.horizontalHeader().setSectionResizeMode(col, mode)
        tbl.verticalHeader().setVisible(False)
        _style_table(tbl, mono_cols=[1, 2, 3])
        lay.addWidget(tbl)
        w._table = tbl
        return w

    def _make_imsi_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        tbl = QTableWidget(0, 3)
        tbl.setHorizontalHeaderLabels(["Slot #", "Raw (9 bytes hex)", "IMSI (decoded)"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        _style_table(tbl, mono_cols=[1, 2])
        lay.addWidget(tbl)
        w._table = tbl
        return w

    def _make_files_tab(self) -> QWidget:
        """Split pane: file list on left, parsed detail on right."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: file list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.addWidget(QLabel("Files in DF Multi-IMSI:"))
        self._file_list = QListWidget()
        self._file_list.setFixedWidth(220)
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        ll.addWidget(self._file_list)
        splitter.addWidget(left)

        # Right: parsed detail
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.addWidget(QLabel("Parsed file content (ETSI decoded):"))
        self._file_detail = QTextEdit()
        self._file_detail.setReadOnly(True)
        self._file_detail.setFont(QFont("Courier New", 9))
        self._file_detail.setStyleSheet(
            "QTextEdit { background: #1e1e1e; color: #d4d4d4; border: none; }"
        )
        rl.addWidget(self._file_detail)
        splitter.addWidget(right)

        splitter.setSizes([220, 600])
        lay.addWidget(splitter)
        return w

    # ── refresh logic ─────────────────────────────────────────────────────────

    def refresh(self) -> None:
        if self._card is None or self._thread is not None:
            return
        self._set_status("Reading card files…", "#1565c0")
        self._btn_refresh.setEnabled(False)
        self._progress.setVisible(True)

        thread = QThread()
        reader = _Reader(self._card)
        reader.moveToThread(thread)
        thread.started.connect(reader.run)
        reader.done.connect(self._on_data)
        reader.error.connect(self._on_error)
        reader.done.connect(thread.quit)
        reader.error.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._reader = reader
        thread.start()

    def _on_thread_finished(self):
        self._thread = None
        self._reader = None

    def _on_data(self, results: dict):
        self._raw_results = results
        self._progress.setVisible(False)
        self._btn_refresh.setEnabled(True)

        self._populate_config(results.get(EF_CONFIG))
        self._populate_mcc(results.get(EF_MCC_LIST))
        self._populate_imsi(results.get(EF_IMSI_LIST))
        self._populate_file_list(results)

        ok = sum(1 for v in results.values() if v is not None)
        total = len(results)
        self._set_status(f"Read {ok}/{total} files successfully", "#2e7d32")

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._btn_refresh.setEnabled(True)
        self._set_status(f"Read error: {msg}", "#c62828")

    # ── populate helpers ──────────────────────────────────────────────────────

    def _populate_config(self, data: bytes | None) -> None:
        tbl = self._tab_config._table
        tbl.setRowCount(0)
        rows = _parse_ef_config(data) if data else [("Error", "—", "No data returned")]
        for field, value, desc in rows:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, _item(field, bold=True))
            tbl.setItem(r, 1, _item(value, color="#1a237e"))
            tbl.setItem(r, 2, _item(desc, color="#555555"))

    def _populate_mcc(self, data: bytes | None) -> None:
        tbl = self._tab_mcc._table
        tbl.setRowCount(0)
        if data is None:
            self._mcc_count_lbl.setText("Could not read 4F03")
            return
        entries = _parse_mcc_list(data)
        self._mcc_count_lbl.setText(f"{len(entries)} entries found in EF_MCC_List (4F03)")
        for e in entries:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, _item(str(e["num"])))
            tbl.setItem(r, 1, _item(e["plmn_hex"], mono=True,
                                    color="#880e4f" if e["invalid"] else "#4a148c"))
            tbl.setItem(r, 2, _item(e["mcc"], mono=True))
            tbl.setItem(r, 3, _item(e["mnc"], mono=True))
            tbl.setItem(r, 4, _item(e["country"] or "—",
                                    color="#e65100" if not e["country"] else "#2e7d32"))
            wild_txt = "Yes" if e["wildcard"] else "No"
            tbl.setItem(r, 5, _item(wild_txt,
                                    color="#e65100" if e["wildcard"] else "#000"))
            idx_txt = str(e["idx"]) + (e["idx_note"] or "")
            tbl.setItem(r, 6, _item(idx_txt, bold=True, color="#1565c0"))
            # Row background: amber for wildcard, pink for invalid-MCC entries
            bg = None
            if e["invalid"]:
                bg = QColor("#fce4ec")
            elif e["wildcard"]:
                bg = QColor("#fff8e1")
            if bg:
                for c in range(7):
                    it = tbl.item(r, c)
                    if it:
                        it.setBackground(bg)

    def _populate_imsi(self, data: bytes | None) -> None:
        tbl = self._tab_imsi._table
        tbl.setRowCount(0)
        if data is None:
            tbl.insertRow(0)
            tbl.setItem(0, 0, _item("—"))
            tbl.setItem(0, 1, _item("—"))
            tbl.setItem(0, 2, _item("Could not read 4F07"))
            return
        entries = _parse_imsi_list(data)
        for slot, raw, imsi in entries:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, _item(str(slot), bold=True))
            tbl.setItem(r, 1, _item(raw, mono=True, color="#4a148c"))
            tbl.setItem(r, 2, _item(imsi, mono=True, color="#1b5e20"))

    def _populate_file_list(self, results: dict) -> None:
        self._file_list.clear()
        self._file_detail.clear()

        # Core files
        for fid, label, note in [
            (EF_CONFIG,   "4F01 — Config",    ""),
            (EF_MCC_LIST, "4F03 — MCC List",  ""),
            (EF_IMSI_LIST,"4F07 — IMSI List", ""),
        ]:
            data = results.get(fid)
            txt = f"{label}  [{len(data)} B]" if data else f"{label}  [not found]"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, fid)
            item.setForeground(QColor("#2e7d32" if data else "#c62828"))
            self._file_list.addItem(item)

        # Other files
        for fid, name, _ in OTHER_FILES:
            data = results.get(fid)
            txt = f"{fid} — {name}  [{len(data)} B]" if data else f"{fid} — {name}  [not found]"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, fid)
            item.setForeground(QColor("#2e7d32" if data else "#c62828"))
            self._file_list.addItem(item)

    def _on_file_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self._file_list.item(row)
        if not item:
            return
        fid = item.data(Qt.ItemDataRole.UserRole)
        data = self._raw_results.get(fid)
        self._file_detail.setPlainText(self._format_file(fid, data))

    def _format_file(self, fid: str, data: bytes | None) -> str:
        if data is None:
            return f"File {fid}: not found on card."
        lines = [f"File ID: {fid}   Size: {len(data)} bytes", "─" * 60]

        if fid == EF_CONFIG:
            for field, value, desc in _parse_ef_config(data):
                lines.append(f"  {field:<24} {value:<30} {desc}")

        elif fid == EF_MCC_LIST:
            entries = _parse_mcc_list(data)
            lines.append(f"  Total entries: {len(entries)}")
            lines.append("")
            lines.append(f"  {'#':<4} {'PLMN':<8} {'MCC':<5} {'MNC':<6} {'Country':<30} {'Wild':<5} {'IMSI'}")
            lines.append("  " + "─" * 72)
            for e in entries:
                lines.append(
                    f"  {e['num']:<4} {e['plmn_hex']:<8} {e['mcc']:<5} {e['mnc']:<6} "
                    f"{(e['country'] or '—'):<30} {'Y' if e['wildcard'] else 'N':<5} "
                    f"{e['idx']}{e['idx_note']}"
                )

        elif fid == EF_IMSI_LIST:
            entries = _parse_imsi_list(data)
            lines.append(f"  Total IMSI slots: {len(entries)}")
            for slot, raw, imsi in entries:
                lines.append(f"  Slot {slot}: {raw}  →  {imsi}")

        elif fid == "4F42":   # SMSP
            # Try to guess record length (43 is standard for 3 profiles in 129 bytes)
            for rec_len in (43, 40, 52, 28):
                if len(data) % rec_len == 0:
                    break
            else:
                rec_len = 43
            records = _parse_smsp_list(data, rec_len)
            lines.append(f"  Record length: {rec_len} bytes   Records: {len(data) // rec_len}")
            for rec in records:
                if "error" in rec:
                    lines.append(f"\n  Slot {rec.get('slot','?')}: {rec['error']}")
                    continue
                lines.append(f"\n  ── Slot {rec['slot']} ──────────────────────────")
                lines.append(f"  Alpha ID:         {rec['alpha']}")
                lines.append(f"  SMSC Number:      {rec['smsc']}")
                lines.append(f"  TP-Param Ind:     {rec['tp_pi']}  "
                              f"(SC={'Y' if rec['pi_valid']['TP-SC'] else 'N'} "
                              f"DA={'Y' if rec['pi_valid']['TP-DA'] else 'N'} "
                              f"PID={'Y' if rec['pi_valid']['TP-PID'] else 'N'} "
                              f"DCS={'Y' if rec['pi_valid']['TP-DCS'] else 'N'})")
                lines.append(f"  TP-PID:           {rec['tp_pid']}")
                lines.append(f"  TP-DCS:           {rec['tp_dcs']}")
                lines.append(f"  SC Addr (raw):    {rec['raw_sca']}")

        elif fid == "4F0C":   # SPN List
            entries = _parse_spn_list(data)
            lines.append(f"  SPN entry size: 17 bytes   Slots: {len(data) // 17}")
            for slot, name, cond in entries:
                lines.append(f"  Slot {slot}: '{name}'  (display: {cond})")

        elif fid == "4F78":   # ACC List
            entries = _parse_acc_list(data)
            lines.append(f"  ACC entry size: 2 bytes   Slots: {len(data) // 2}")
            for slot, raw, classes in entries:
                lines.append(f"  Slot {slot}: {raw}  Access Classes: {classes}")

        elif fid == "4F7B":   # FPLMN List
            entries = _parse_fplmn_list(data)
            lines.append(f"  FPLMN entry size: 12 bytes (4 PLMNs each)  Slots: {len(entries)}")
            for slot, plmns in entries:
                lines.append(f"  Slot {slot}: {', '.join(plmns) or '(all empty)'}")

        else:
            # Generic: hex dump
            lines.append("  Hex dump (16 bytes per line):")
            stripped = data.rstrip(b"\xFF")
            for off in range(0, len(stripped), 16):
                chunk = stripped[off:off + 16]
                hex_part = " ".join(f"{b:02X}" for b in chunk)
                asc_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
                lines.append(f"  {off:04X}:  {hex_part:<47}  {asc_part}")
            if len(data) > len(stripped):
                lines.append(f"  ... {len(data) - len(stripped)} trailing FF bytes (padding)")

        return "\n".join(lines)

    # ── utilities ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = "#000") -> None:
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _clear_all(self) -> None:
        for tab in [self._tab_config, self._tab_mcc, self._tab_imsi]:
            tab._table.setRowCount(0)
        self._file_list.clear()
        self._file_detail.clear()


# ── shared item helpers ───────────────────────────────────────────────────────

def _item(text: str, bold: bool = False,
          color: str | None = None, mono: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
    if bold:
        f = it.font(); f.setBold(True); it.setFont(f)
    if color:
        it.setForeground(QColor(color))
    if mono:
        it.setFont(QFont("Courier New", 9))
    return it


def _style_table(tbl: QTableWidget, mono_cols: list[int] | None = None) -> None:
    tbl.setStyleSheet(
        "QTableWidget { color: #000; }"
        "QTableWidget::item:selected { color: #000; background: #b3d4f5; }"
    )
    if mono_cols:
        mono_font = QFont("Courier New", 9)
        for col in mono_cols:
            for row in range(tbl.rowCount()):
                it = tbl.item(row, col)
                if it:
                    it.setFont(mono_font)
