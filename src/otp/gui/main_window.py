"""Main window: menu bar + status bar + table/detail splitter."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import Qt, Slot, QThread, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QSplitter,
    QStatusBar, QVBoxLayout, QWidget, QApplication, QMessageBox,
)

from .styles import C, FONTS
from .trip_table import TripTable
from .detail_panel import DetailPanel
from .lan_modal import LanModal
from .workers import TripLoaderWorker, LanRelayWorker
from .trip_model import TripItem, TripState, STATE_LABELS

ROOT = Path(__file__).resolve().parents[2]


class DriveSyncWorker(QThread):
    """Background worker for Google Drive sync."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, action: str, parent=None) -> None:
        super().__init__(parent)
        self._action = action

    def run(self) -> None:
        try:
            from ..drive_sync import DriveSync
            ds = DriveSync()
            if self._action == "status":
                self.finished.emit(ds.get_sync_status())
            elif self._action == "sync":
                evidence_dir = ROOT / "evidence"
                ledger_path = evidence_dir / "ledger.jsonl"
                results = []
                if ledger_path.exists():
                    results.append(ds.sync_ledger(ledger_path))
                if evidence_dir.exists():
                    results.extend(ds.sync_evidence_dir(evidence_dir))
                self.finished.emit({"results": results})
            elif self._action == "disconnect":
                ds.disconnect()
                self.finished.emit({"disconnected": True})
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Operational Trust Pipeline")
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)
        self._trips: list[TripItem] = []
        self._current_relay_url: str | None = None
        self._current_relay_token: str | None = None
        self._lan_worker: LanRelayWorker | None = None
        self._loader: TripLoaderWorker | None = None
        self._build_ui()
        self._build_menus()
        self._build_status_bar()
        self._load_trips()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top summary bar
        self._summary_bar = self._build_summary_bar()
        layout.addWidget(self._summary_bar)

        # Splitter: table on top, detail on bottom
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = TripTable()
        self._table.tripSelected.connect(self._on_trip_selected)
        self._splitter.addWidget(self._table)

        self._detail = DetailPanel()
        self._detail.requestAck.connect(self._on_request_ack)
        self._detail.markReviewed.connect(self._on_mark_reviewed)
        self._detail.viewEvidence.connect(self._on_view_evidence)
        self._detail.copyHash.connect(self._on_copy_hash)
        self._splitter.addWidget(self._detail)

        self._splitter.setSizes([250, 400])
        layout.addWidget(self._splitter, 1)

    def _build_summary_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {C.SURFACE_RAISED}; border-bottom: 1px solid {C.BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        self._counts: dict[str, QLabel] = {}
        for state in [TripState.CRITICAL, TripState.AT_RISK, TripState.WAITING_ACK, TripState.DELIVERY_UNCERTAIN, TripState.RESOLVED]:
            color = {
                TripState.CRITICAL: C.RED,
                TripState.AT_RISK: C.ORANGE,
                TripState.WAITING_ACK: C.ORANGE,
                TripState.DELIVERY_UNCERTAIN: C.GRAY,
                TripState.RESOLVED: C.GREEN,
            }[state]

            dot = QLabel("\u25cf")
            dot.setStyleSheet(f"color: {color}; font-size: 12px;")
            count = QLabel("0")
            count.setFont(QFont(FONTS["mono"], 12, QFont.Weight.Bold))
            count.setStyleSheet(f"color: {color};")
            name = QLabel(STATE_LABELS[state])
            name.setStyleSheet(f"color: {C.TEXT_DIM}; font-size: 11px;")

            row = QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(dot)
            row.addWidget(count)
            row.addWidget(name)
            layout.addLayout(row)

        layout.addStretch()
        return bar

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # Archivo
        file_menu = menubar.addMenu("&Archivo")

        open_action = QAction("&Open Evidence...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_evidence)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Receipt...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_receipt)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        # Google Drive sync
        drive_menu = menubar.addMenu("&Drive")

        drive_auth_action = QAction("&Connect Google Account...", self)
        drive_auth_action.triggered.connect(self._on_drive_auth)
        drive_menu.addAction(drive_auth_action)

        drive_sync_action = QAction("&Sync Evidence to Drive", self)
        drive_sync_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        drive_sync_action.triggered.connect(self._on_drive_sync)
        drive_menu.addAction(drive_sync_action)

        drive_status_action = QAction("Sync &Status", self)
        drive_status_action.triggered.connect(self._on_drive_status)
        drive_menu.addAction(drive_status_action)

        drive_menu.addSeparator()

        drive_disconnect_action = QAction("&Disconnect", self)
        drive_disconnect_action.triggered.connect(self._on_drive_disconnect)
        drive_menu.addAction(drive_disconnect_action)

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Ver
        view_menu = menubar.addMenu("&Ver")

        ack_action = QAction("&Request Acknowledgement", self)
        ack_action.setShortcut(QKeySequence("Ctrl+L"))
        ack_action.triggered.connect(self._on_request_ack)
        view_menu.addAction(ack_action)

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._load_trips)
        view_menu.addAction(refresh_action)

        view_menu.addSeparator()

        filter_critical = QAction("Filter: &Critical Only", self)
        filter_critical.triggered.connect(self._filter_critical)
        view_menu.addAction(filter_critical)

        filter_all = QAction("Filter: &Show All", self)
        filter_all.triggered.connect(self._filter_all)
        view_menu.addAction(filter_all)

        view_menu.addSeparator()

        ledger_action = QAction("View &Ledger...", self)
        ledger_action.triggered.connect(self._on_view_ledger)
        view_menu.addAction(ledger_action)

        # Ayuda
        help_menu = menubar.addMenu("&Ayuda")

        about_action = QAction("&About OTP", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        docs_action = QAction("&Documentation", self)
        docs_action.triggered.connect(self._on_open_docs)
        help_menu.addAction(docs_action)

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # Drive sync indicator
        self._drive_label = QLabel("Drive: not connected")
        self._drive_label.setStyleSheet(f"color: {C.GRAY}; font-size: 11px; margin-right: 8px;")
        self._status_bar.addPermanentWidget(self._drive_label)

        # Check Drive auth status on startup
        self._check_drive_status()

    def _check_drive_status(self) -> None:
        """Check if Drive is authenticated on startup."""
        try:
            from ..drive_sync import DriveSync
            ds = DriveSync()
            if ds.is_authenticated():
                self._drive_label.setText("Drive: connected")
                self._drive_label.setStyleSheet(f"color: {C.GREEN}; font-size: 11px;")
        except Exception:
            pass

    # --- Data loading ---

    def _load_trips(self) -> None:
        self._status_bar.showMessage("Loading RoadStar data...")
        self._loader = TripLoaderWorker(self)
        self._loader.finished.connect(self._on_trips_loaded)
        self._loader.error.connect(self._on_load_error)
        self._loader.start()

    @Slot(list)
    def _on_trips_loaded(self, trips: list) -> None:
        self._trips = trips
        self._table.setTrips(trips)
        self._update_counts()
        self._status_bar.showMessage(f"Loaded {len(trips)} trips", 5000)

    @Slot(str)
    def _on_load_error(self, msg: str) -> None:
        self._status_bar.showMessage(f"Error: {msg}", 10000)

    def _update_counts(self) -> None:
        counts = {s: 0 for s in TripState}
        for t in self._trips:
            counts[t.state] += 1
        for state, lbl in self._counts.items():
            s = TripState(state)
            lbl.setText(str(counts.get(s, 0)))

    # --- Table selection ---

    @Slot(object)
    def _on_trip_selected(self, trip: TripItem | None) -> None:
        self._detail.setTrip(trip)

    # --- Actions ---

    def _on_request_ack(self) -> None:
        trip = self._table.selectedTrip()
        if trip is None:
            return

        # Start relay if not running
        if self._current_relay_url is None:
            from ..lan_relay import start_relay
            host, port, token = start_relay()
            self._current_relay_url = f"http://127.0.0.1:{port}"
            self._current_relay_token = token

        modal = LanModal(trip, self._current_relay_url, self._current_relay_token, self)
        modal.rejected.connect(lambda: self._cancel_lan_worker())

        # Inject request into relay
        from ..lan_relay import inject_request
        req = modal.getRequest()
        inject_request(modal.getRequestID(), req)

        # Start polling worker
        self._lan_worker = LanRelayWorker(
            self._current_relay_url, self._current_relay_token,
            modal.getRequestID(), timeout=300.0, parent=self
        )
        self._lan_worker.response.connect(modal.on_response)
        self._lan_worker.error.connect(lambda e: self._on_lan_error(e, modal))
        self._lan_worker.start()

        modal.exec()

    def _cancel_lan_worker(self) -> None:
        if self._lan_worker:
            self._lan_worker.cancel()
            self._lan_worker = None

    @Slot(str, object)
    def _on_lan_error(self, error: str, modal: LanModal) -> None:
        if error == "HUMAN_TIMEOUT":
            modal.on_response({"acknowledged": False, "message": "", "received_at": time.time()})

    def _on_mark_reviewed(self) -> None:
        trip = self._table.selectedTrip()
        if trip is None:
            return
        trip.state = TripState.RESOLVED
        trip.ack_status = "acknowledged"
        self._table.setTrips(self._trips)
        self._detail.setTrip(trip)
        self._update_counts()

    def _on_view_evidence(self) -> None:
        trip = self._detail._trip
        if trip and trip.receipt_hash:
            # Show receipt hash in a message box
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Evidence Receipt", f"Receipt hash:\n{trip.receipt_hash}")

    def _on_copy_hash(self) -> None:
        h = self._detail.getReceiptHash()
        if h:
            QApplication.clipboard().setText(h)
            self._status_bar.showMessage("Hash copied to clipboard", 3000)

    def _on_open_evidence(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Evidence Receipt", str(ROOT), "JSON Files (*.json)"
        )
        if path:
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                # Display in status bar
                h = data.get("receipt_sha256", "unknown")
                self._status_bar.showMessage(f"Loaded receipt: {h[:16]}...", 5000)
            except Exception as e:
                self._status_bar.showMessage(f"Error loading: {e}", 5000)

    def _on_save_receipt(self) -> None:
        trip = self._detail._trip
        if trip is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Receipt", str(ROOT / f"receipt_{trip.trip_id}.json"), "JSON Files (*.json)"
        )
        if path:
            from ..evidence import make_receipt
            from ..pipeline import AckLeasePolicy, FixedClock
            ev = trip.raw_event
            if ev:
                run_dict = {
                    "execution_id": f"exec_{trip.trip_id}",
                    "event": ev,
                    "lease": {"state": "SATISFIED"},
                    "finding": {"reason_code": trip.finding_code, "reason": trip.finding_message},
                    "verdict": type("V", (), {"value": "ACTION_REQUESTED"})(),
                    "action": None,
                    "result": {"status": "ACKNOWLEDGED", "delivery": "KNOWN"},
                    "policy_version": "ack-lease-v0",
                    "source_adapter": "roadstar-workbook-v0",
                    "channel_adapter": "lan-channel/1",
                }
                receipt = make_receipt(run_dict)
                Path(path).write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
                self._status_bar.showMessage(f"Saved: {path}", 5000)

    def _filter_critical(self) -> None:
        filtered = [t for t in self._trips if t.state in (TripState.CRITICAL, TripState.AT_RISK)]
        self._table.setTrips(filtered)
        self._status_bar.showMessage(f"Showing {len(filtered)} critical/at-risk trips", 3000)

    def _filter_all(self) -> None:
        self._table.setTrips(self._trips)
        self._status_bar.showMessage(f"Showing all {len(self._trips)} trips", 3000)

    def _on_view_ledger(self) -> None:
        ledger_path = ROOT / "evidence" / "ledger.jsonl"
        if ledger_path.exists():
            from PySide6.QtWidgets import QTextEdit, QDialog
            dlg = QDialog(self)
            dlg.setWindowTitle("Ledger")
            dlg.resize(600, 400)
            text = QTextEdit()
            text.setPlainText(ledger_path.read_text(encoding="utf-8"))
            text.setReadOnly(True)
            layout = QVBoxLayout(dlg)
            layout.addWidget(text)
            dlg.exec()
        else:
            self._status_bar.showMessage("No ledger found", 3000)

    def _on_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self, "About OTP",
            "Operational Trust Pipeline v0.1.0\n\n"
            "Provider-agnostic bounded operational action requests\n"
            "with verifiable evidence.\n\n"
            "Hackathon demo: RoadStar data \u2192 OTP \u2192 Local device \u2192 ACK \u2192 Receipt"
        )

    def _on_open_docs(self) -> None:
        import os
        os.startfile(str(ROOT / "docs"))

    def _on_drive_auth(self) -> None:
        """Authenticate with Google Drive."""
        from PySide6.QtWidgets import QInputDialog
        email, ok = QInputDialog.getText(
            self, "Google Drive",
            "Enter your Google email to authenticate:\n\n"
            "1. Go to console.cloud.google.com\n"
            "2. Create project > Enable Drive API\n"
            "3. Create OAuth2 credentials (Desktop app)\n"
            "4. Download credentials.json to ~/.otp/credentials.json\n\n"
            "Email:"
        )
        if ok and email:
            self._drive_label.setText("Authenticating...")
            self._drive_label.setStyleSheet(f"color: {C.BLUE}; font-size: 11px;")
            worker = DriveSyncWorker("auth", self)
            worker.finished.connect(lambda r: self._on_drive_auth_done(r, email))
            worker.error.connect(self._on_drive_error)
            self._drive_worker = worker
            worker.start()

    def _on_drive_auth_done(self, result: dict, email: str) -> None:
        self._drive_label.setText(f"Drive: {email}")
        self._drive_label.setStyleSheet(f"color: {C.GREEN}; font-size: 11px;")
        self._status_bar.showMessage("Google Drive connected", 5000)

    def _on_drive_sync(self) -> None:
        """Sync evidence to Google Drive."""
        self._drive_label.setText("Syncing...")
        self._drive_label.setStyleSheet(f"color: {C.BLUE}; font-size: 11px;")
        worker = DriveSyncWorker("sync", self)
        worker.finished.connect(self._on_drive_sync_done)
        worker.error.connect(self._on_drive_error)
        self._drive_worker = worker
        worker.start()

    def _on_drive_sync_done(self, result: dict) -> None:
        results = result.get("results", [])
        uploaded = sum(1 for r in results if r.get("status") in ("created", "updated"))
        unchanged = sum(1 for r in results if r.get("status") == "unchanged")
        errors = sum(1 for r in results if r.get("status") == "error")
        self._drive_label.setText(f"Drive: {uploaded} uploaded, {unchanged} unchanged")
        self._drive_label.setStyleSheet(f"color: {C.GREEN}; font-size: 11px;")
        msg = f"Synced: {uploaded} uploaded, {unchanged} unchanged"
        if errors:
            msg += f", {errors} errors"
        self._status_bar.showMessage(msg, 5000)

    def _on_drive_status(self) -> None:
        """Show sync status."""
        worker = DriveSyncWorker("status", self)
        worker.finished.connect(self._on_drive_status_done)
        worker.error.connect(self._on_drive_error)
        self._drive_worker = worker
        worker.start()

    def _on_drive_status_done(self, status: dict) -> None:
        from PySide6.QtWidgets import QMessageBox
        auth = "Connected" if status.get("authenticated") else "Not connected"
        count = status.get("upload_count", 0)
        last = status.get("last_sync", "never")
        QMessageBox.information(
            self, "Drive Sync Status",
            f"Status: {auth}\n"
            f"Total uploads: {count}\n"
            f"Last sync: {last}"
        )

    def _on_drive_disconnect(self) -> None:
        """Disconnect from Google Drive."""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Disconnect Drive",
            "Remove Google Drive connection?\n"
            "Local evidence is not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            worker = DriveSyncWorker("disconnect", self)
            worker.finished.connect(lambda: self._on_drive_disconnected())
            worker.error.connect(self._on_drive_error)
            self._drive_worker = worker
            worker.start()

    def _on_drive_disconnected(self) -> None:
        self._drive_label.setText("Drive: not connected")
        self._drive_label.setStyleSheet(f"color: {C.GRAY}; font-size: 11px;")
        self._status_bar.showMessage("Google Drive disconnected", 3000)

    def _on_drive_error(self, error: str) -> None:
        self._drive_label.setText("Drive: error")
        self._drive_label.setStyleSheet(f"color: {C.RED}; font-size: 11px;")
        self._status_bar.showMessage(f"Drive error: {error}", 5000)
