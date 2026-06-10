from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton
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

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Test Cases")
        self._tree.setColumnCount(1)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("Unselect All")
        btn_none.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)

        layout.addLayout(btn_row)
        layout.addWidget(self._tree)

    def _populate(self):
        self._tree.clear()
        # Group by domain
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
