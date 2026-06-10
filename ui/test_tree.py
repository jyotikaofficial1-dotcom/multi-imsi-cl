from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from runner.registry import TestRegistry


class TestTree(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._registry = TestRegistry()
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("Unselect All")
        btn_none.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Test Cases")
        self._tree.setColumnCount(1)
        self._tree.currentItemChanged.connect(self._on_item_changed)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)

        self._desc_box = QLabel("Select a test case to see its description.")
        self._desc_box.setWordWrap(True)
        self._desc_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._desc_box.setStyleSheet(
            "QLabel { background: #f5f5f5; border: 1px solid #ccc; "
            "padding: 6px; color: #333; font-size: 11px; }"
        )
        self._desc_box.setFixedHeight(72)

        layout.addLayout(btn_row)
        layout.addWidget(self._tree, stretch=1)
        layout.addWidget(sep)
        layout.addWidget(self._desc_box)

    def _on_item_changed(self, current, _previous):
        if current is None:
            self._desc_box.setText("Select a test case to see its description.")
            return
        tc_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not tc_id:
            # domain header clicked
            self._desc_box.setText(f"<b>{current.text(0)}</b> — domain group")
            return
        cls = self._registry.get_class(tc_id) if tc_id in self._registry.all_ids() else None
        if cls:
            desc = getattr(cls, 'description', '')
            title = getattr(cls, 'title', tc_id)
            priority = getattr(cls, 'priority', '')
            header = f"<b>{tc_id}</b> [{priority}] — {title}"
            if desc:
                self._desc_box.setText(f"{header}<br><small>{desc}</small>")
            else:
                self._desc_box.setText(header)
        else:
            self._desc_box.setText(current.text(0))

    def _populate(self):
        self._tree.clear()
        domains: dict[str, list] = {}
        for tc_id in sorted(self._registry.all_ids()):
            cls = self._registry.get_class(tc_id) if tc_id in self._registry.all_ids() else None
            if cls:
                domain = getattr(cls, 'domain', 'Other')
                domains.setdefault(domain, []).append((tc_id, cls))

        for domain, tests in sorted(domains.items()):
            parent = QTreeWidgetItem(self._tree, [domain])
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Checked)
            for tc_id, cls in tests:
                title = getattr(cls, 'title', tc_id)
                desc = getattr(cls, 'description', '')
                child = QTreeWidgetItem(parent, [f"{tc_id} — {title}"])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
                child.setData(0, Qt.ItemDataRole.UserRole, tc_id)
                if desc:
                    child.setToolTip(0, desc)
            parent.setExpanded(True)

    def selected_ids(self) -> list[str]:
        ids = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            domain_item = root.child(i)
            for j in range(domain_item.childCount()):
                child = domain_item.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    tc_id = child.data(0, Qt.ItemDataRole.UserRole)
                    if tc_id:
                        ids.append(tc_id)
        return ids

    def _select_all(self):
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            domain_item = root.child(i)
            for j in range(domain_item.childCount()):
                domain_item.child(j).setCheckState(0, Qt.CheckState.Checked)
            domain_item.setCheckState(0, Qt.CheckState.Checked)

    def _clear_all(self):
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            domain_item = root.child(i)
            for j in range(domain_item.childCount()):
                domain_item.child(j).setCheckState(0, Qt.CheckState.Unchecked)
            domain_item.setCheckState(0, Qt.CheckState.Unchecked)
