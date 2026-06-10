from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from transport.reader_manager import ReaderManager
from transport.connection import CardConnection
from engine.card_io import CardIO
import tests.card_config as card_config
import os


class ReaderPanel(QWidget):
    connected = pyqtSignal(object)       # CardIO
    disconnected = pyqtSignal()
    log_message = pyqtSignal(str, str)   # (text, color) → APDU console

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rm = ReaderManager()
        self._conn: CardConnection | None = None
        self._card: CardIO | None = None
        self._build_ui()

    def _build_ui(self):
        group = QGroupBox("Reader Connection")
        layout = QVBoxLayout(group)

        # Row 1: reader selector
        row1 = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(70)
        btn_refresh.clicked.connect(self._refresh_readers)
        row1.addWidget(QLabel("Reader:"))
        row1.addWidget(self._combo, stretch=1)
        row1.addWidget(btn_refresh)

        # Row 2: connect + ATR
        row2 = QHBoxLayout()
        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setFixedWidth(90)
        self._btn_connect.clicked.connect(self._toggle_connect)
        self._atr_label = QLineEdit()
        self._atr_label.setReadOnly(True)
        self._atr_label.setPlaceholderText("ATR will appear here")
        self._atr_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        row2.addWidget(self._btn_connect)
        row2.addWidget(self._atr_label, stretch=1)

        # Row 3: ADM key + proactive session button
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("ADM Key (hex):"))
        self._adm_input = QLineEdit()
        self._adm_input.setPlaceholderText("e.g. 3733323339313637  (16 hex chars = 8 bytes)")
        self._adm_input.setMaxLength(32)
        self._adm_input.setStyleSheet("font-family: monospace;")
        self._btn_adm = QPushButton("Verify ADM")
        self._btn_adm.setFixedWidth(100)
        self._btn_adm.setEnabled(False)
        self._btn_adm.clicked.connect(self._verify_adm)
        self._btn_tp = QPushButton("▶ Proactive Init")
        self._btn_tp.setFixedWidth(120)
        self._btn_tp.setEnabled(False)
        self._btn_tp.setToolTip(
            "Send TERMINAL PROFILE then drain pending STK commands\n"
            "(FETCH + TERMINAL RESPONSE loop until SW ≠ 91 XX)"
        )
        self._btn_tp.clicked.connect(self._run_proactive)
        self._adm_status = QLabel("—")
        self._adm_status.setFixedWidth(160)
        row3.addWidget(self._adm_input, stretch=1)
        row3.addWidget(self._btn_adm)
        row3.addWidget(self._btn_tp)
        row3.addWidget(self._adm_status)

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)

        self._refresh_readers()

    def _refresh_readers(self):
        self._combo.clear()
        readers = self._rm.list_readers()
        if readers:
            self._combo.addItems(readers)
        else:
            self._combo.addItem("— no readers found —")

    def _toggle_connect(self):
        if self._conn is None:
            self._do_connect()
        else:
            self._do_disconnect()

    def _do_connect(self):
        idx = self._combo.currentIndex()
        if idx < 0:
            return
        try:
            raw_conn = self._rm.connect(idx)
            self._conn = CardConnection(raw_conn)
            self._card = CardIO(self._conn)
            atr = self._rm.get_atr(raw_conn)
            self._atr_label.setText(atr)
            self._btn_connect.setText("Disconnect")
            self._btn_adm.setEnabled(True)
            self._btn_tp.setEnabled(True)
            self._adm_status.setText("Not verified")
            self._adm_status.setStyleSheet("color: #e65100;")

            # Run full proactive session (TP + FETCH loop)
            self._run_proactive(auto=True)

            # Discover AIDs from EF DIR and cache in card_config
            self._discover_aids()

            # Auto-verify ADM if key already entered
            key = self._adm_input.text().strip().replace(" ", "")
            if len(key) in (16, 32):
                self._verify_adm()

            self.connected.emit(self._card)
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def _do_disconnect(self):
        if self._conn:
            self._conn.disconnect()
        self._conn = None
        self._card = None
        self._atr_label.clear()
        self._btn_connect.setText("Connect")
        self._btn_adm.setEnabled(False)
        self._btn_tp.setEnabled(False)
        self._adm_status.setText("—")
        self._adm_status.setStyleSheet("")
        self.disconnected.emit()

    def _discover_aids(self):
        """Read EF DIR (2F00) to find USIM/ISIM AIDs and update card_config."""
        if self._card is None:
            return
        try:
            aids = self._card.read_ef_dir()
            card_config.set_discovered_aids(aids)
            usim = aids.get("USIM", "")
            isim = aids.get("ISIM", "")
            if usim:
                self.log_message.emit(f"EF DIR → USIM AID: {usim}", "#888888")
            if isim:
                self.log_message.emit(f"EF DIR → ISIM AID: {isim}", "#888888")
            if not usim and not isim:
                self.log_message.emit("EF DIR → no USIM/ISIM AID found (using fallback)", "#e65100")
        except Exception as e:
            self.log_message.emit(f"EF DIR discovery error: {e}", "#f44747")

    def _run_proactive(self, auto: bool = False):
        """Send TERMINAL PROFILE and drain STK queue (FETCH/TR loop)."""
        if self._card is None:
            return
        try:
            log_lines = self._card.run_proactive_session()
            color = "#888888" if auto else "#4a90d9"
            for line in log_lines:
                self.log_message.emit(line, color)
            # Show brief status on button
            self._btn_tp.setText("✓ Proactive Init")
            self._btn_tp.setStyleSheet("color: #2e7d32;")
        except Exception as e:
            self.log_message.emit(f"Proactive session error: {e}", "#f44747")
            if not auto:
                QMessageBox.warning(self, "Proactive Session Error", str(e))

    def _verify_adm(self):
        if self._card is None:
            return
        key = self._adm_input.text().strip().replace(" ", "")
        if len(key) not in (16, 32):
            QMessageBox.warning(self, "ADM Key Error",
                                "ADM key must be 16 hex chars (8 bytes) or 32 hex chars (16 bytes).")
            return
        try:
            resp = self._card.verify_adm(key)
            if resp.sw == 0x9000:
                self._adm_status.setText("✓ ADM verified")
                self._adm_status.setStyleSheet("color: #2e7d32; font-weight: bold;")
            elif resp.sw1 == 0x91:
                # Another proactive command pending — drain then retry
                self._run_proactive(auto=True)
                resp = self._card.verify_adm(key)
                if resp.sw == 0x9000:
                    self._adm_status.setText("✓ ADM verified")
                    self._adm_status.setStyleSheet("color: #2e7d32; font-weight: bold;")
                else:
                    self._adm_status.setText(f"✗ SW={resp.sw_hex}")
                    self._adm_status.setStyleSheet("color: #c62828;")
            elif resp.sw1 == 0x63:
                retries = resp.sw2 & 0x0F
                self._adm_status.setText(f"✗ Wrong key ({retries} left)")
                self._adm_status.setStyleSheet("color: #c62828;")
                QMessageBox.warning(self, "ADM Verify Failed",
                                    f"Wrong ADM key. {retries} retries remaining.")
            else:
                self._adm_status.setText(f"✗ SW={resp.sw_hex}")
                self._adm_status.setStyleSheet("color: #c62828;")
                QMessageBox.warning(self, "ADM Verify Failed",
                                    f"Card returned SW={resp.sw_hex}")
        except Exception as e:
            QMessageBox.critical(self, "ADM Error", str(e))

    def is_connected(self) -> bool:
        return self._conn is not None

    def card_io(self) -> CardIO | None:
        return self._card

    def get_atr(self) -> str:
        return self._atr_label.text()
