from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PyQt6.QtCore import Qt


class APDUConsole(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        self._label = QPushButton("APDU Log")
        self._label.setEnabled(False)
        self._label.setFlat(True)
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(60)
        btn_clear.clicked.connect(self.clear)
        btn_row.addWidget(self._label)
        btn_row.addStretch()
        btn_row.addWidget(btn_clear)

        self._edit = QPlainTextEdit()
        self._edit.setReadOnly(True)
        font = QFont("Courier New", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._edit.setFont(font)
        self._edit.setMaximumBlockCount(5000)

        layout.addLayout(btn_row)
        layout.addWidget(self._edit)

    def append_apdu(self, tc_id: str, sent_hex: str, response_hex: str):
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        def append_colored(text: str, color: str):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.insertText(text, fmt)

        append_colored(f"[{tc_id}] ", "#888888")
        if sent_hex:
            append_colored(f"TX: {sent_hex}\n", "#2e7d32")
        if response_hex:
            is_fail = not (response_hex.strip().endswith("[9000]") or
                           response_hex.strip().endswith("9000"))
            color = "#c62828" if is_fail else "#1565c0"
            append_colored(f"RX: {response_hex}\n", color)

        self._edit.setTextCursor(cursor)
        self._edit.ensureCursorVisible()

    def append_message(self, text: str, color: str = "#333333"):
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)
        self._edit.setTextCursor(cursor)
        self._edit.ensureCursorVisible()

    def clear(self):
        self._edit.clear()
