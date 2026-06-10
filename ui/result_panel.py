from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


STATUS_COLORS = {
    "PASS": QColor("#e8f5e9"),
    "FAIL": QColor("#ffebee"),
    "SKIP": QColor("#f5f5f5"),
    "ERROR": QColor("#fff3e0"),
}


class ResultPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._summary = QLabel("No results yet")
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["TC ID", "Domain", "Title", "Status", "Duration (ms)"]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)

        layout.addWidget(self._summary)
        layout.addWidget(self._table)

    def add_result(self, result):
        self._results.append(result)
        row = self._table.rowCount()
        self._table.insertRow(row)

        items = [
            result.tc_id,
            result.domain,
            result.title,
            result.status.value,
            f"{result.duration_ms:.1f}",
        ]
        bg = STATUS_COLORS.get(result.status.value, QColor("#ffffff"))
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setBackground(bg)
            if col == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, col, item)

        self._table.scrollToBottom()
        self._update_summary()

    def _update_summary(self):
        passed = sum(1 for r in self._results if r.status.value == "PASS")
        failed = sum(1 for r in self._results if r.status.value == "FAIL")
        total = len(self._results)
        self._summary.setText(
            f"Results: {total} total — {passed} PASS / {failed} FAIL"
        )

    def all_results(self):
        return list(self._results)

    def clear_results(self):
        self._results.clear()
        self._table.setRowCount(0)
        self._summary.setText("No results yet")
