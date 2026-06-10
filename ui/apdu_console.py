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
        btn_clear = QPushButton("Clear Log")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self.clear)
        btn_row.addStretch()
        btn_row.addWidget(btn_clear)

        self._edit = QPlainTextEdit()
        self._edit.setReadOnly(True)
        font = QFont("Courier New", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._edit.setFont(font)
        self._edit.setMaximumBlockCount(5000)
        # Force white background + black text so colored output is always visible
        self._edit.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
            "border: 1px solid #444; }"
        )

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
            append_colored(f"TX: {sent_hex}\n", "#4ec9b0")   # teal
        if response_hex:
            is_ok = (response_hex.strip().endswith("[9000]") or
                     response_hex.strip().endswith("9000"))
            color = "#f44747" if not is_ok else "#6a9955"     # red / green
            append_colored(f"RX: {response_hex}\n", color)

        self._edit.setTextCursor(cursor)
        self._edit.ensureCursorVisible()

    def append_message(self, text: str, color: str = "#d4d4d4"):
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)
        self._edit.setTextCursor(cursor)
        self._edit.ensureCursorVisible()

    def clear(self):
        self._edit.clear()
