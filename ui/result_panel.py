from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QFrame
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
        layout.setSpacing(4)

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
        self._table.setStyleSheet(
            "QTableWidget { color: #000000; font-size: 12px; }"
            "QTableWidget::item { color: #000000; }"
            "QTableWidget::item:selected { background-color: #b3d4f5; color: #000000; }"
        )
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        # Description bar — shown when a row is selected
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        self._desc_label = QLabel("← Click a result row to see its description")
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet(
            "QLabel { background: #f5f5f5; border: 1px solid #ccc; "
            "padding: 6px; color: #333; font-size: 11px; min-height: 36px; }"
        )

        layout.addWidget(self._summary)
        layout.addWidget(self._table, stretch=1)
        layout.addWidget(sep)
        layout.addWidget(self._desc_label)

    def _on_selection_changed(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._desc_label.setText("← Click a result row to see its description")
            return
        row = rows[0].row()
        if row < len(self._results):
            result = self._results[row]
            desc = getattr(result, 'description', '')
            tc_id = result.tc_id
            title = result.title
            if desc:
                self._desc_label.setText(f"<b>{tc_id} — {title}</b><br>{desc}")
            else:
                self._desc_label.setText(f"<b>{tc_id} — {title}</b>")

    def add_result(self, result):
        self._results.append(result)
        row = self._table.rowCount()
        self._table.insertRow(row)

        description = getattr(result, 'description', '')
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
            if col == 2 and description:
                item.setToolTip(description)
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
        self._desc_label.setText("← Click a result row to see its description")
