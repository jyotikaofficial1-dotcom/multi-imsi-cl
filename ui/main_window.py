"""Main application window for the Multi-IMSI Test Tool."""
from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QCloseEvent, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QPushButton, QFileDialog,
    QMessageBox, QStatusBar, QLabel, QProgressBar,
    QToolBar
)

from ui.reader_panel import ReaderPanel
from ui.test_tree import TestTree
from ui.apdu_console import APDUConsole
from ui.result_panel import ResultPanel
from ui.apdu_sender import APDUSender
from ui.card_info_panel import CardInfoPanel
from runner.test_runner import TestRunner
from runner.result import TestResult
from reports.html_report import HTMLReporter
from reports.json_export import JSONExporter
from reports.csv_export import CSVExporter


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _RunWorker(QObject):
    """Runs selected test cases on a background QThread."""

    result_ready = pyqtSignal(object)   # TestResult
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, runner: TestRunner, tc_ids: list[str]):
        super().__init__()
        self._runner = runner
        self._tc_ids = tc_ids
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            for tc_id in self._tc_ids:
                if self._cancelled:
                    break
                result = self._runner.run_single(tc_id)
                self.result_ready.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Top-level window that hosts reader, test-selection, and result panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._runner: TestRunner | None = None
        self._worker: _RunWorker | None = None
        self._thread: QThread | None = None

        self.setWindowTitle("Multi-IMSI Test Tool")
        self.resize(1200, 780)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._set_running(False)
        # Wire reader panel log signal after all widgets are constructed
        self._reader_panel.log_message.connect(self._apdu_console.append_message)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # --- Reader panel (top) ---
        self._reader_panel = ReaderPanel()
        self._reader_panel.connected.connect(self._on_connected)
        self._reader_panel.disconnected.connect(self._on_disconnected)
        root.addWidget(self._reader_panel)

        # --- Main splitter: left tree | right tabs ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: test selection tree
        self._test_tree = TestTree()
        main_splitter.addWidget(self._test_tree)

        # Right: tabbed result + APDU console + manual sender
        right_tabs = QTabWidget()
        self._result_panel = ResultPanel()
        self._apdu_console = APDUConsole()
        self._apdu_sender = APDUSender()
        self._apdu_sender.log_message.connect(
            lambda text, color: self._apdu_console.append_message(text, color)
        )
        self._card_info = CardInfoPanel()
        right_tabs.addTab(self._result_panel, "Results")
        right_tabs.addTab(self._card_info,    "Card Info")
        right_tabs.addTab(self._apdu_console, "APDU Log")
        right_tabs.addTab(self._apdu_sender,  "Manual APDU")
        main_splitter.addWidget(right_tabs)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([280, 900])

        root.addWidget(main_splitter, stretch=1)

        # --- Bottom button bar ---
        btn_bar = QHBoxLayout()
        self._btn_run = QPushButton("▶  Run Selected")
        self._btn_run.setEnabled(False)
        self._btn_run.clicked.connect(self._start_run)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_run)

        self._btn_clear = QPushButton("Clear Results")
        self._btn_clear.clicked.connect(self._clear_results)

        self._btn_export_html = QPushButton("Export HTML…")
        self._btn_export_html.setEnabled(False)
        self._btn_export_html.clicked.connect(self._export_html)

        self._btn_export_json = QPushButton("Export JSON…")
        self._btn_export_json.setEnabled(False)
        self._btn_export_json.clicked.connect(self._export_json)

        self._btn_export_csv = QPushButton("Export CSV…")
        self._btn_export_csv.setEnabled(False)
        self._btn_export_csv.clicked.connect(self._export_csv)

        self._btn_export_log = QPushButton("Export Log…")
        self._btn_export_log.setEnabled(False)
        self._btn_export_log.clicked.connect(self._export_log)

        btn_bar.addWidget(self._btn_run)
        btn_bar.addWidget(self._btn_stop)
        btn_bar.addStretch()
        btn_bar.addWidget(self._btn_clear)
        btn_bar.addWidget(self._btn_export_html)
        btn_bar.addWidget(self._btn_export_json)
        btn_bar.addWidget(self._btn_export_csv)
        btn_bar.addWidget(self._btn_export_log)
        root.addLayout(btn_bar)

    def _build_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        act_export_html = QAction("Export &HTML Report…", self)
        act_export_html.setShortcut("Ctrl+S")
        act_export_html.triggered.connect(self._export_html)
        file_menu.addAction(act_export_html)

        act_export_json = QAction("Export &JSON Report…", self)
        act_export_json.triggered.connect(self._export_json)
        file_menu.addAction(act_export_json)

        act_export_csv = QAction("Export &CSV Report…", self)
        act_export_csv.triggered.connect(self._export_csv)
        file_menu.addAction(act_export_csv)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Run menu
        run_menu = menubar.addMenu("&Run")

        self._act_run = QAction("&Run Selected", self)
        self._act_run.setShortcut("F5")
        self._act_run.setEnabled(False)
        self._act_run.triggered.connect(self._start_run)
        run_menu.addAction(self._act_run)

        self._act_stop = QAction("&Stop", self)
        self._act_stop.setShortcut("F6")
        self._act_stop.setEnabled(False)
        self._act_stop.triggered.connect(self._stop_run)
        run_menu.addAction(self._act_stop)

        run_menu.addSeparator()

        act_clear = QAction("&Clear Results", self)
        act_clear.triggered.connect(self._clear_results)
        run_menu.addAction(act_clear)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._tb_run = tb.addAction("▶ Run")
        self._tb_run.setEnabled(False)
        self._tb_run.triggered.connect(self._start_run)

        self._tb_stop = tb.addAction("■ Stop")
        self._tb_stop.setEnabled(False)
        self._tb_stop.triggered.connect(self._stop_run)

        tb.addSeparator()

        tb_clear = tb.addAction("Clear")
        tb_clear.triggered.connect(self._clear_results)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Not connected")
        sb.addWidget(self._status_label, stretch=1)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)

    # ------------------------------------------------------------------
    # Connection callbacks
    # ------------------------------------------------------------------

    def _on_connected(self, card_io):
        self._runner = TestRunner(
            card=card_io,
            progress_cb=None,   # results come via Qt signals from worker
        )
        self._runner.discover()
        self._apdu_sender.set_card(card_io)
        self._card_info.set_card(card_io)
        self._status_label.setText(
            f"Connected — ATR: {self._reader_panel.get_atr()}"
        )
        self._set_running(False)
        self._btn_run.setEnabled(True)
        self._act_run.setEnabled(True)
        self._tb_run.setEnabled(True)
        self._apdu_console.append_message(
            f"Card connected. ATR: {self._reader_panel.get_atr()}", "#1565c0"
        )

    def _on_disconnected(self):
        self._runner = None
        self._apdu_sender.set_card(None)
        self._card_info.set_card(None)
        self._status_label.setText("Not connected")
        self._btn_run.setEnabled(False)
        self._act_run.setEnabled(False)
        self._tb_run.setEnabled(False)
        self._apdu_console.append_message("Card disconnected.", "#888888")

    # ------------------------------------------------------------------
    # Run / stop
    # ------------------------------------------------------------------

    def _start_run(self):
        if self._runner is None:
            QMessageBox.warning(self, "Not Connected", "Please connect a card reader first.")
            return

        tc_ids = self._test_tree.selected_ids()
        if not tc_ids:
            QMessageBox.information(self, "No Tests Selected", "Select at least one test case to run.")
            return

        self._result_panel.clear_results()
        # Do NOT clear the APDU log here — user clears it manually
        self._apdu_console.append_message(
            f"── Starting run: {len(tc_ids)} test(s) ──", "#4a90d9"
        )

        self._set_running(True)
        self._progress.setMaximum(len(tc_ids))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status_label.setText(f"Running 0 / {len(tc_ids)}…")

        # Reset runner state from previous run
        self._runner.reset()

        # Create worker and thread
        self._thread = QThread(self)
        self._worker = _RunWorker(self._runner, tc_ids)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.error.connect(self._on_run_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _stop_run(self):
        if self._worker:
            self._worker.cancel()
            self._apdu_console.append_message("Stop requested…", "#e65100")

    def _on_result(self, result: TestResult):
        self._result_panel.add_result(result)

        # Log all APDUs captured at CardIO level
        if self._runner and self._runner._card:
            log = self._runner._card.get_apdu_log()
            self._runner._card.clear_apdu_log()
            for tx, rx in log:
                self._apdu_console.append_apdu(result.tc_id, tx, rx)
        # Fallback: log from step records if no CardIO log
        else:
            for step in result.steps:
                if step.apdu_sent or step.response:
                    self._apdu_console.append_apdu(
                        result.tc_id, step.apdu_sent, step.response
                    )

        # Update progress
        done = self._result_panel._table.rowCount()
        total = self._progress.maximum()
        self._progress.setValue(done)
        self._status_label.setText(f"Running {done} / {total}…")

        color = "#2e7d32" if result.status.value == "PASS" else (
            "#c62828" if result.status.value == "FAIL" else "#888888"
        )
        self._apdu_console.append_message(
            f"  [{result.tc_id}] {result.title}: {result.status.value}", color
        )

        # Enable export as soon as we have at least one result
        self._btn_export_html.setEnabled(True)
        self._btn_export_json.setEnabled(True)
        self._btn_export_csv.setEnabled(True)
        self._btn_export_log.setEnabled(True)

    def _on_run_finished(self):
        self._set_running(False)
        self._progress.setVisible(False)
        results = self._result_panel.all_results()
        passed = sum(1 for r in results if r.status.value == "PASS")
        total = len(results)
        self._status_label.setText(
            f"Run complete — {passed}/{total} passed"
        )
        self._apdu_console.append_message(
            f"Run complete: {passed}/{total} passed.", "#1565c0"
        )

    def _on_run_error(self, msg: str):
        QMessageBox.critical(self, "Runner Error", msg)
        self._apdu_console.append_message(f"ERROR: {msg}", "#c62828")

    def _set_running(self, running: bool):
        self._btn_run.setEnabled(not running)
        self._btn_stop.setEnabled(running)
        self._act_run.setEnabled(not running)
        self._act_stop.setEnabled(running)
        self._tb_run.setEnabled(not running)
        self._tb_stop.setEnabled(running)

    # ------------------------------------------------------------------
    # Clear / export
    # ------------------------------------------------------------------

    def _clear_results(self):
        self._result_panel.clear_results()
        self._apdu_console.clear()
        self._btn_export_html.setEnabled(False)
        self._btn_export_json.setEnabled(False)
        self._btn_export_csv.setEnabled(False)
        self._btn_export_log.setEnabled(False)
        self._status_label.setText(
            f"Connected — ATR: {self._reader_panel.get_atr()}"
            if self._reader_panel.is_connected()
            else "Not connected"
        )

    def _default_filename(self, ext: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"multi_imsi_{stamp}.{ext}"

    def _export_html(self):
        results = self._result_panel.all_results()
        if not results:
            QMessageBox.information(self, "No Results", "There are no results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export HTML Report", self._default_filename("html"),
            "HTML Files (*.html)"
        )
        if path:
            try:
                HTMLReporter(results, self._reader_panel.get_atr()).save(path)
                self._status_label.setText(f"HTML report saved: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _export_json(self):
        results = self._result_panel.all_results()
        if not results:
            QMessageBox.information(self, "No Results", "There are no results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON Report", self._default_filename("json"),
            "JSON Files (*.json)"
        )
        if path:
            try:
                JSONExporter(results, self._reader_panel.get_atr()).save(path)
                self._status_label.setText(f"JSON report saved: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _export_csv(self):
        results = self._result_panel.all_results()
        if not results:
            QMessageBox.information(self, "No Results", "There are no results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV Report", self._default_filename("csv"),
            "CSV Files (*.csv)"
        )
        if path:
            try:
                CSVExporter(results).save(path)
                self._status_label.setText(f"CSV report saved: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _export_log(self):
        text = self._apdu_console.get_text()
        if not text.strip():
            QMessageBox.information(self, "No Log", "APDU log is empty.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export APDU Log", self._default_filename("txt"),
            "Text Files (*.txt)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self._status_label.setText(f"Log saved: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent):
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(3000)
        if self._reader_panel.is_connected():
            self._reader_panel._do_disconnect()
        event.accept()
