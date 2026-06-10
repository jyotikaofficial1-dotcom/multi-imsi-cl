from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QPlainTextEdit, QGroupBox, QComboBox
)
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PyQt6.QtCore import Qt, pyqtSignal


# Common APDUs for quick access
QUICK_APDUS = [
    ("-- Quick APDUs --", ""),
    ("SELECT MF",             "00 A4 00 0C 02 3F 00"),
    ("SELECT DF GSM",         "00 A4 00 0C 02 7F 20"),
    ("SELECT DF Multi-IMSI",  "00 A4 00 0C 02 7F 30"),
    ("SELECT DF 5F1A",        "00 A4 00 0C 02 5F 1A"),
    ("SELECT EF_IMSI (6F07)", "00 A4 00 0C 02 6F 07"),
    ("SELECT EF_Config (4F01)","00 A4 00 0C 02 4F 01"),
    ("READ BINARY 0,16",      "00 B0 00 00 10"),
    ("READ BINARY 0,32",      "00 B0 00 00 20"),
    ("READ RECORD 1",         "00 B2 01 04 00"),
    ("GET RESPONSE 0x10",     "00 C0 00 00 10"),
    ("TERMINAL PROFILE",      "80 10 00 00 0C FF FF FF FF FF FF FF FF FF FF FF FF"),
    ("FETCH (len=0)",         "80 12 00 00 00"),
]


class APDUSender(QWidget):
    """Manual APDU sender panel."""

    log_message = pyqtSignal(str, str)   # (text, color) — forwarded to APDU console

    def __init__(self, parent=None):
        super().__init__(parent)
        self._card = None
        self._build_ui()

    def set_card(self, card):
        self._card = card
        self._btn_send.setEnabled(card is not None)
        self._status.setText("Card connected — enter an APDU and click Send." if card
                             else "Not connected.")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Quick APDU picker
        quick_group = QGroupBox("Quick APDUs")
        quick_layout = QHBoxLayout(quick_group)
        self._quick_combo = QComboBox()
        for label, _ in QUICK_APDUS:
            self._quick_combo.addItem(label)
        self._quick_combo.currentIndexChanged.connect(self._on_quick_select)
        quick_layout.addWidget(self._quick_combo)
        root.addWidget(quick_group)

        # APDU input
        input_group = QGroupBox("APDU (hex bytes, space-separated or continuous)")
        input_layout = QVBoxLayout(input_group)

        self._apdu_input = QLineEdit()
        self._apdu_input.setFont(QFont("Courier New", 10))
        self._apdu_input.setPlaceholderText("e.g.  00 A4 00 0C 02 3F 00")
        self._apdu_input.returnPressed.connect(self._send)

        btn_row = QHBoxLayout()
        self._btn_send = QPushButton("Send APDU")
        self._btn_send.setFixedWidth(110)
        self._btn_send.setEnabled(False)
        self._btn_send.clicked.connect(self._send)
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.setFixedWidth(90)
        btn_clear_log.clicked.connect(self._clear_log)
        btn_row.addWidget(self._btn_send)
        btn_row.addWidget(btn_clear_log)
        btn_row.addStretch()

        input_layout.addWidget(self._apdu_input)
        input_layout.addLayout(btn_row)
        root.addWidget(input_group)

        # Response log
        log_group = QGroupBox("Response Log")
        log_layout = QVBoxLayout(log_group)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier New", 9))
        self._log.setStyleSheet(
            "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; border: none; }"
        )
        self._log.setMaximumBlockCount(2000)
        log_layout.addWidget(self._log)
        root.addWidget(log_group, stretch=1)

        # Status bar
        self._status = QLabel("Not connected.")
        self._status.setStyleSheet("color: #666; font-size: 11px;")
        root.addWidget(self._status)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_quick_select(self, idx: int):
        if idx <= 0:
            return
        _, apdu_hex = QUICK_APDUS[idx]
        if apdu_hex:
            self._apdu_input.setText(apdu_hex)
        self._quick_combo.setCurrentIndex(0)

    def _send(self):
        if self._card is None:
            self._status.setText("Not connected.")
            return
        raw = self._apdu_input.text().strip().replace(" ", "")
        if not raw:
            return
        if len(raw) % 2 != 0:
            self._status.setText("Error: odd number of hex characters.")
            return
        try:
            apdu_bytes = bytes.fromhex(raw)
        except ValueError:
            self._status.setText("Error: invalid hex characters.")
            return
        if len(apdu_bytes) < 4:
            self._status.setText("Error: APDU must be at least 4 bytes (CLA INS P1 P2).")
            return

        tx_display = " ".join(f"{b:02X}" for b in apdu_bytes)
        self._append(f"TX: {tx_display}", "#4ec9b0")

        try:
            from engine.apdu import APDU
            # Build APDU: header + optional Lc+data + Le
            header = apdu_bytes[:4]
            body = apdu_bytes[4:]
            if body:
                lc = body[0]
                data = body[1:1+lc]
                le_bytes = body[1+lc:]
                le = le_bytes[0] if le_bytes else None
                apdu = APDU(header[0], header[1], header[2], header[3], data, le=le)
            else:
                apdu = APDU(header[0], header[1], header[2], header[3])

            resp = self._card.transmit(apdu)
            rx_data = resp.data.hex().upper() if resp.data else ""
            rx_sw = resp.sw_hex
            rx_display = f"{rx_data}  SW: {rx_sw}" if rx_data else f"SW: {rx_sw}"
            color = "#6a9955" if resp.sw == 0x9000 else (
                "#4ec9b0" if resp.sw1 == 0x61 else "#f44747"
            )
            self._append(f"RX: {rx_display}", color)
            self._status.setText(f"Last SW: {rx_sw}")

            # Also emit to APDU console tab
            self.log_message.emit(f"[Manual] TX: {tx_display}", "#4ec9b0")
            self.log_message.emit(f"[Manual] RX: {rx_display}", color)

        except Exception as exc:
            self._append(f"ERROR: {exc}", "#f44747")
            self._status.setText(f"Error: {exc}")

    def _append(self, text: str, color: str):
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

    def _clear_log(self):
        self._log.clear()
