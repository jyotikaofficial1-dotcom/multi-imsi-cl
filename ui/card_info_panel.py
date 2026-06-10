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
    QGroupBox, QTextEdit, QSizePolicy, QProgressBar
)


# ── file IDs ────────────────────────────────────────────────────────────────
DF_MULTI    = "7F305F1A"
EF_CONFIG   = "4F01"
EF_MCC_LIST = "4F03"
EF_IMSI_LIST= "4F07"

OTHER_FILES = [
    ("4F0C", "SPN List",         48,  "3 profiles × 17 bytes"),
    ("4F42", "SMSP List",        129, "3 profiles × 43 bytes"),
    ("4F62", "HPLMNwAcT List",   0,   "3 profiles × EF size"),
    ("4F78", "ACC List",         6,   "3 profiles × 2 bytes"),
    ("4F7B", "FPLMN List",       120, "3 profiles × 12 bytes"),
    ("007B", "FPLMN ADF List",   0,   "3 profiles × EF size"),
    ("4F32", "IMPI List (ISIM)", 0,   "optional"),
    ("4F33", "DOMAIN List",      0,   "optional"),
    ("4F34", "IMPU List",        0,   "optional"),
    ("4F57", "SUCI Calc Info",   0,   "optional 5G"),
    ("4F58", "OPL5G List",       0,   "optional 5G"),
]


# ── PLMN / IMSI helpers ─────────────────────────────────────────────────────

def _decode_plmn_bytes(b: bytes) -> tuple[str, str, bool]:
    """
    Decode 3-byte GSM-encoded PLMN into (mcc, mnc, is_wildcard).
    Nibble value 0xD is the proprietary wildcard used in EF 4F03.
    Nibble value 0xF is the standard filler (padding for 2-digit MNC).
    """
    WILD = 0xD
    n = [b[0] & 0xF, (b[0] >> 4) & 0xF,   # MCC[0], MCC[1]
         b[1] & 0xF, (b[1] >> 4) & 0xF,    # MCC[2], MNC[2]
         b[2] & 0xF, (b[2] >> 4) & 0xF]    # MNC[0], MNC[1]

    def _nib(v: int) -> str:
        if v == WILD: return "D"
        if v == 0xF:  return "F"
        return str(v)

    mcc = _nib(n[0]) + _nib(n[1]) + _nib(n[2])
    mnc_raw = [n[4], n[5], n[3]]            # MNC[0], MNC[1], MNC[2]
    if mnc_raw[2] == 0xF:                   # 2-digit MNC
        mnc = _nib(mnc_raw[0]) + _nib(mnc_raw[1])
    else:
        mnc = _nib(mnc_raw[0]) + _nib(mnc_raw[1]) + _nib(mnc_raw[2])

    wildcard = any(v == WILD for v in n)
    return mcc, mnc, wildcard


def _decode_imsi(b: bytes) -> str:
    """Decode 9-byte BCD IMSI from EF_IMSI / EF_IMSI_List entry."""
    if len(b) < 2:
        return "—"
    nibbles = []
    for byte in b[1:]:
        nibbles.append(byte & 0xF)
        nibbles.append((byte >> 4) & 0xF)
    digits = nibbles[1:]            # skip parity nibble
    while digits and digits[-1] == 0xF:
        digits.pop()
    return "".join(str(d) for d in digits) or "—"


def _bool_str(b: int) -> str:
    return "Enabled" if b else "Disabled"


def _parse_ef_config(data: bytes) -> list[tuple[str, str, str]]:
    """
    Parse EF Configuration (4F01) into list of (field, value, description).
    Returns as many fields as the data allows; stops on IndexError.
    """
    rows: list[tuple[str, str, str]] = []
    if not data:
        return [("Error", "—", "No data returned")]
    try:
        off = 0
        def rb(n=1):
            nonlocal off
            v = data[off:off+n]
            off += n
            return v

        rows.append(("Applet Mode",        _bool_str(rb()[0]),             "0x01=enabled, 0x00=disabled"))
        rows.append(("Automatic Mode",     _bool_str(rb()[0]),             "auto IMSI switching"))
        rows.append(("Active IMSI Index",  str(rb()[0]),                   "currently active profile"))
        rows.append(("Periodic Switching", _bool_str(rb()[0]),             "periodic STATUS check"))
        rows.append(("Periodic Counter",   str(rb()[0]),                   "STATUS commands between checks"))
        rows.append(("Max IMSI Profiles",  str(rb()[0]),                   "max supported profiles (≤10)"))
        rows.append(("Round Robin",        _bool_str(rb()[0]),             "round-robin on network loss"))
        rb()  # RFU
        x = rb()[0]
        rows.append(("Menu Text Length",   str(x),                         "bytes of STK menu label"))
        try:
            text = rb(x).decode("ascii", errors="replace")
        except Exception:
            text = "—"
        rows.append(("Menu Text",          text,                           "STK main menu label"))
        rows.append(("Poll Interval",      f"{rb()[0]} s",                 "STATUS polling interval"))
        rb(); rb(); rb()    # 3 × RFU
        rows.append(("Fallback Counter",   str(rb()[0]),                   "STATUS count before fallback"))
        rows.append(("Fallback Mode",      _bool_str(rb()[0]),             "fallback mode flag"))
        rb()    # RFU
        rows.append(("Refresh Type",       f"0x{rb()[0]:02X}",            "REFRESH qualifier"))
        rows.append(("Default LOCI Flag",  str(rb()[0]),                   "use PLMN for LOCI init"))
        y = rb()[0]
        rows.append(("PoR Config Length",  str(y),                         "bytes of PoR config"))
        if y:
            por = rb(y).hex().upper()
            rows.append(("PoR Config",     por,                            "PoR record update spec"))
        u = rb()[0]
        rows.append(("ISIM AID Length",    str(u),                         "0=not present"))
        if 0x0A <= u <= 0x10:
            rows.append(("ISIM AID",       rb(u).hex().upper(),            "ADF ISIM application ID"))
        s = rb()[0]
        rows.append(("USIM AID Length",    str(s),                         "0=not present"))
        if 0x0A <= s <= 0x10:
            rows.append(("USIM AID",       rb(s).hex().upper(),            "ADF USIM application ID"))
    except (IndexError, Exception) as e:
        rows.append(("(parse stopped)",    str(e),                         ""))
    return rows


def _parse_mcc_list(data: bytes) -> list[tuple[int, str, str, str, str, int]]:
    """
    Parse EF MCC Mapping List (4F03).
    Returns list of (index, plmn_hex, mcc, mnc, wildcard_label, imsi_idx).
    Stops at all-FF or all-00 entry.
    """
    entries = []
    i = 0
    n = 0
    while i + 3 < len(data):
        plmn = data[i:i+3]
        idx  = data[i+3]
        i += 4
        if plmn == b"\xFF\xFF\xFF" or idx == 0xFF:
            break
        if plmn == b"\x00\x00\x00":
            break
        n += 1
        mcc, mnc, wild = _decode_plmn_bytes(plmn)
        entries.append((n, plmn.hex().upper(), mcc, mnc,
                        "Yes" if wild else "No", idx))
    return entries


def _parse_imsi_list(data: bytes, max_profiles: int = 10) -> list[tuple[int, str, str]]:
    """
    Parse EF IMSI List (4F07).
    Each slot = 9 bytes.  Returns list of (slot_no, raw_hex, decoded_imsi).
    """
    entries = []
    for i in range(max_profiles):
        off = i * 9
        if off + 9 > len(data):
            break
        slot = data[off:off+9]
        if slot == b"\xFF" * 9 or slot == b"\x00" * 9:
            continue
        entries.append((i + 1, slot.hex().upper(), _decode_imsi(slot)))
    return entries


# ── background reader ────────────────────────────────────────────────────────

class _Reader(QObject):
    done    = pyqtSignal(dict)   # {file_id: bytes | None}
    error   = pyqtSignal(str)

    def __init__(self, card):
        super().__init__()
        self._card = card

    def run(self):
        results: dict[str, bytes | None] = {}
        try:
            c = self._card
            for fid in [EF_CONFIG, EF_MCC_LIST, EF_IMSI_LIST]:
                try:
                    c.select_by_path(DF_MULTI)
                    c.select_by_id(fid)
                    size = {"4F01": 64, "4F03": 500, "4F07": 90}[fid]
                    data = c.read_binary_chunked(size)
                    results[fid] = data
                except Exception as e:
                    results[fid] = None

            for fid, *_ in OTHER_FILES:
                try:
                    c.select_by_path(DF_MULTI)
                    c.select_by_id(fid)
                    data = c.read_binary_chunked(256)
                    results[fid] = data
                except Exception:
                    results[fid] = None

        except Exception as e:
            self.error.emit(str(e))
            return
        self.done.emit(results)


# ── panel ────────────────────────────────────────────────────────────────────

class CardInfoPanel(QWidget):
    """Displays parsed content of all DF Multi-IMSI files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._card = None
        self._thread: QThread | None = None
        self._reader: _Reader | None = None
        self._build_ui()

    # ── public API ───────────────────────────────────────────────────────────

    def set_card(self, card) -> None:
        self._card = card
        if card:
            self.refresh()
        else:
            self._set_status("Not connected", "#888888")
            self._clear_all()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Header bar
        hdr = QHBoxLayout()
        title = QLabel("Card Personalisation Data")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._status_lbl = QLabel("Not connected")
        self._status_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        self._btn_refresh = QPushButton("🔄 Refresh")
        self._btn_refresh.setFixedWidth(100)
        self._btn_refresh.setEnabled(False)
        self._btn_refresh.clicked.connect(self.refresh)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(14)
        self._progress.setVisible(False)
        hdr.addWidget(title)
        hdr.addWidget(self._status_lbl, stretch=1)
        hdr.addWidget(self._progress)
        hdr.addWidget(self._btn_refresh)
        root.addLayout(hdr)

        # Sub-tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tab_config   = self._make_config_tab()
        self._tab_mcc      = self._make_mcc_tab()
        self._tab_imsi     = self._make_imsi_tab()
        self._tab_files    = self._make_files_tab()

        self._tabs.addTab(self._tab_config, "Config (4F01)")
        self._tabs.addTab(self._tab_mcc,    "MCC List (4F03)")
        self._tabs.addTab(self._tab_imsi,   "IMSI List (4F07)")
        self._tabs.addTab(self._tab_files,  "All Files")

        root.addWidget(self._tabs, stretch=1)

    # -- per-tab factory methods -------------------------------------------

    def _make_config_tab(self) -> QWidget:
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
        tbl.setStyleSheet("QTableWidget { color: #000; } "
                          "QTableWidget::item:selected { color: #000; background: #b3d4f5; }")
        lay.addWidget(tbl)
        w._table = tbl
        return w

    def _make_mcc_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        info = QLabel("Each entry: 3 bytes PLMN (GSM 04.08) + 1 byte IMSI Index.  "
                      "Nibble 'D' = wildcard (matches any digit).  "
                      "Nibble 'F' = filler (2-digit MNC).")
        info.setStyleSheet("color: #555; font-size: 11px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        tbl = QTableWidget(0, 6)
        tbl.setHorizontalHeaderLabels(
            ["#", "PLMN (hex)", "MCC", "MNC", "Wildcard", "IMSI Index"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for col, mode in enumerate([
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.Stretch,
        ]):
            tbl.horizontalHeader().setSectionResizeMode(col, mode)
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { color: #000; } "
                          "QTableWidget::item:selected { color: #000; background: #b3d4f5; }")
        lay.addWidget(tbl)
        w._table = tbl
        return w

    def _make_imsi_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        tbl = QTableWidget(0, 3)
        tbl.setHorizontalHeaderLabels(["Slot #", "Raw (hex)", "IMSI (decoded)"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { color: #000; font-family: monospace; } "
                          "QTableWidget::item:selected { color: #000; background: #b3d4f5; }")
        lay.addWidget(tbl)
        w._table = tbl
        return w

    def _make_files_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(["File ID", "Name", "Status", "Hex Preview (first 32 bytes)"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setFont(QFont("Courier New", 9))
        tbl.setStyleSheet("QTableWidget { color: #000; } "
                          "QTableWidget::item:selected { color: #000; background: #b3d4f5; }")
        lay.addWidget(tbl)
        w._table = tbl
        return w

    # ── refresh logic ────────────────────────────────────────────────────────

    def refresh(self) -> None:
        if self._card is None:
            return
        if self._thread and self._thread.isRunning():
            return

        self._set_status("Reading card files…", "#1565c0")
        self._btn_refresh.setEnabled(False)
        self._progress.setVisible(True)

        self._thread = QThread(self)
        self._reader = _Reader(self._card)
        self._reader.moveToThread(self._thread)
        self._thread.started.connect(self._reader.run)
        self._reader.done.connect(self._on_data)
        self._reader.error.connect(self._on_error)
        self._reader.done.connect(self._thread.quit)
        self._reader.done.connect(self._reader.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_data(self, results: dict):
        self._progress.setVisible(False)
        self._btn_refresh.setEnabled(True)

        self._populate_config(results.get(EF_CONFIG))
        self._populate_mcc(results.get(EF_MCC_LIST))
        self._populate_imsi(results.get(EF_IMSI_LIST))
        self._populate_files(results)

        ok = sum(1 for v in results.values() if v is not None)
        total = len(results)
        self._set_status(f"Read {ok}/{total} files successfully", "#2e7d32")

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._btn_refresh.setEnabled(True)
        self._set_status(f"Error: {msg}", "#c62828")

    # ── populate helpers ─────────────────────────────────────────────────────

    def _populate_config(self, data: bytes | None) -> None:
        tbl = self._tab_config._table
        tbl.setRowCount(0)
        if data is None:
            self._add_row(tbl, ["(failed)", "—", "Could not read 4F01"])
            return
        for field, value, desc in _parse_ef_config(data):
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, self._item(field, bold=True))
            tbl.setItem(row, 1, self._item(value, color="#1a237e"))
            tbl.setItem(row, 2, self._item(desc, color="#555555"))

    def _populate_mcc(self, data: bytes | None) -> None:
        tbl = self._tab_mcc._table
        tbl.setRowCount(0)
        if data is None:
            self._add_row(tbl, ["—"] * 6)
            return
        entries = _parse_mcc_list(data)
        for num, plmn_hex, mcc, mnc, wild, imsi_idx in entries:
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, self._item(str(num)))
            tbl.setItem(row, 1, self._item(plmn_hex, mono=True, color="#4a148c"))
            tbl.setItem(row, 2, self._item(mcc, mono=True))
            tbl.setItem(row, 3, self._item(mnc, mono=True))
            wild_item = self._item(wild, color="#e65100" if wild == "Yes" else "#000")
            tbl.setItem(row, 4, wild_item)
            idx_item = self._item(str(imsi_idx), bold=True, color="#1565c0")
            tbl.setItem(row, 5, idx_item)
            # Colour wildcard rows slightly differently
            if wild == "Yes":
                for c in range(6):
                    it = tbl.item(row, c)
                    if it:
                        it.setBackground(QColor("#fff8e1"))

    def _populate_imsi(self, data: bytes | None) -> None:
        tbl = self._tab_imsi._table
        tbl.setRowCount(0)
        if data is None:
            self._add_row(tbl, ["—", "—", "Could not read 4F07"])
            return
        entries = _parse_imsi_list(data)
        if not entries:
            self._add_row(tbl, ["—", "—", "No IMSI slots found"])
            return
        for slot, raw, imsi in entries:
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, self._item(str(slot), bold=True))
            tbl.setItem(row, 1, self._item(raw, mono=True, color="#4a148c"))
            tbl.setItem(row, 2, self._item(imsi, mono=True, color="#1b5e20"))

    def _populate_files(self, results: dict) -> None:
        tbl = self._tab_files._table
        tbl.setRowCount(0)
        for fid, name, *_ in OTHER_FILES:
            data = results.get(fid)
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, self._item(fid, mono=True, bold=True))
            tbl.setItem(row, 1, self._item(name))
            if data is None:
                tbl.setItem(row, 2, self._item("Not found", color="#c62828"))
                tbl.setItem(row, 3, self._item("—"))
            else:
                # Strip trailing FF bytes for preview
                stripped = data.rstrip(b"\xFF")
                tbl.setItem(row, 2, self._item(f"{len(data)} bytes", color="#2e7d32"))
                preview = stripped[:32].hex().upper()
                if len(stripped) > 32:
                    preview += "…"
                tbl.setItem(row, 3, self._item(preview, mono=True))
        tbl.resizeRowsToContents()

    # ── utilities ────────────────────────────────────────────────────────────

    def _item(self, text: str, bold: bool = False,
              color: str | None = None, mono: bool = False) -> QTableWidgetItem:
        it = QTableWidgetItem(str(text))
        it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        if color:
            it.setForeground(QColor(color))
        if mono:
            it.setFont(QFont("Courier New", 9))
        return it

    def _add_row(self, tbl: QTableWidget, values: list[str]) -> None:
        row = tbl.rowCount()
        tbl.insertRow(row)
        for col, val in enumerate(values):
            tbl.setItem(row, col, self._item(val))

    def _set_status(self, msg: str, color: str = "#000000") -> None:
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _clear_all(self) -> None:
        for tab in [self._tab_config, self._tab_mcc,
                    self._tab_imsi, self._tab_files]:
            tab._table.setRowCount(0)

    # ── enable/disable refresh button when reader connects ───────────────────

    def on_connected(self) -> None:
        self._btn_refresh.setEnabled(True)

    def on_disconnected(self) -> None:
        self._btn_refresh.setEnabled(False)
        self._clear_all()
        self._set_status("Not connected", "#888888")
