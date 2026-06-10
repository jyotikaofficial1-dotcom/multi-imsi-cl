from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QGroupBox, QInputDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from transport.reader_manager import ReaderManager
from transport.connection import CardConnection
from engine.card_io import CardIO
from security.adm_keys import ADMKeyManager
import os


class ReaderPanel(QWidget):
    connected = pyqtSignal(object)     # CardIO
    disconnected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rm = ReaderManager()
        self._conn: CardConnection | None = None
        self._card: CardIO | None = None
        self._adm: ADMKeyManager | None = None
        self._build_ui()

    def _build_ui(self):
        group = QGroupBox("Reader Connection")
        layout = QVBoxLayout(group)

        row1 = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(70)
        btn_refresh.clicked.connect(self._refresh_readers)
        row1.addWidget(QLabel("Reader:"))
        row1.addWidget(self._combo, stretch=1)
        row1.addWidget(btn_refresh)

        row2 = QHBoxLayout()
        self._btn_connect = QPushButton("Connect")
        self._btn_connect.clicked.connect(self._toggle_connect)
        self._atr_label = QLineEdit()
        self._atr_label.setReadOnly(True)
        self._atr_label.setPlaceholderText("ATR will appear here")
        self._atr_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        row2.addWidget(self._btn_connect)
        row2.addWidget(self._atr_label, stretch=1)

        layout.addLayout(row1)
        layout.addLayout(row2)

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

            # Load ADM vault
            vault_path = "security/key_store.enc"
            if os.path.exists(vault_path):
                passphrase, ok = QInputDialog.getText(
                    self, "ADM Vault", "Enter vault passphrase:",
                    QInputDialog.InputMode.Password
                )
                if ok and passphrase:
                    try:
                        self._adm = ADMKeyManager(vault_path, passphrase.encode())
                        self._adm.verify(self._card)
                    except Exception as e:
                        QMessageBox.warning(self, "ADM Error", str(e))
                        self._adm = None

            self.connected.emit(self._card)
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))

    def _do_disconnect(self):
        if self._conn:
            self._conn.disconnect()
        self._conn = None
        self._card = None
        self._adm = None
        self._atr_label.clear()
        self._btn_connect.setText("Connect")
        self.disconnected.emit()

    def is_connected(self) -> bool:
        return self._conn is not None

    def card_io(self) -> CardIO | None:
        return self._card

    def adm_manager(self) -> ADMKeyManager | None:
        return self._adm

    def get_atr(self) -> str:
        return self._atr_label.text()
