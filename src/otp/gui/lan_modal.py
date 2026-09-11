"""LAN modal: request acknowledgement dialog with auto-update."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QFrame, QSizePolicy,
)

from .styles import C, FONTS
from .trip_model import TripItem


class LanModal(QDialog):
    acknowledged = Signal(str)  # emits request_id

    def __init__(self, trip: TripItem, relay_url: str, token: str, parent=None) -> None:
        super().__init__(parent)
        self._trip = trip
        self._relay_url = relay_url
        self._token = token
        self._request_id = f"act_{trip.trip_id}"
        self._polling = False
        self.setWindowTitle("Request Acknowledgement")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Request acknowledgement")
        header.setFont(QFont(FONTS["sans"], 14, QFont.Weight.Bold))
        layout.addWidget(header)

        # Trip info
        info = QLabel(
            f"Trip {self._trip.trip_id} may miss DELIVER_BY\n"
            f"Driver acknowledgement requested"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Status
        self._status_icon = QLabel("\u25cf")
        self._status_icon.setStyleSheet(f"color: {C.ORANGE}; font-size: 14px;")
        self._status_text = QLabel("Waiting for response\u2026")
        self._status_text.setFont(QFont(FONTS["sans"], 11))
        status_row = QHBoxLayout()
        status_row.addWidget(self._status_icon)
        status_row.addWidget(self._status_text)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Device URL
        url_frame = QFrame()
        url_frame.setProperty("class", "card")
        url_frame.setObjectName("card")
        url_layout = QVBoxLayout(url_frame)
        url_layout.setContentsMargins(12, 8, 12, 8)
        url_label = QLabel("Local device")
        url_label.setProperty("dim", True)
        url_layout.addWidget(url_label)
        url_val = QLabel(self._relay_url)
        url_val.setFont(QFont(FONTS["mono"], 10))
        url_layout.addWidget(url_val)
        layout.addWidget(url_frame)

        # Technical details (collapsible)
        self._tech_frame = QFrame()
        self._tech_frame.hide()
        tech_layout = QVBoxLayout(self._tech_frame)
        tech_layout.setContentsMargins(0, 4, 0, 0)
        tech_layout.setSpacing(2)
        self._add_label_row(tech_layout, "Session token:", self._token[:16] + "\u2026")
        self._add_label_row(tech_layout, "Request ID:", self._request_id)
        self._add_label_row(tech_layout, "Relay port:", self._relay_url.split(":")[-1].split("/")[0])
        layout.addWidget(self._tech_frame)

        self._btn_tech = QPushButton("Technical details \u25b8")
        self._btn_tech.setStyleSheet(f"color: {C.BLUE}; border: none; text-align: left; padding: 0;")
        self._btn_tech.clicked.connect(self._toggle_tech)
        layout.addWidget(self._btn_tech)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_close = QPushButton("Close")
        self._btn_close.clicked.connect(self.accept)
        self._btn_close.hide()
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

    def _add_label_row(self, parent_layout: QVBoxLayout, label_text: str, value_text: str) -> None:
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setProperty("dim", True)
        lbl.setFont(QFont(FONTS["mono"], 9))
        val = QLabel(value_text)
        val.setFont(QFont(FONTS["mono"], 9))
        row.addWidget(lbl)
        row.addWidget(val)
        row.addStretch()
        parent_layout.addLayout(row)

    def _toggle_tech(self) -> None:
        if self._tech_frame.isVisible():
            self._tech_frame.hide()
            self._btn_tech.setText("Technical details \u25b8")
        else:
            self._tech_frame.show()
            self._btn_tech.setText("Technical details \u25c2")

    @Slot(dict)
    def on_response(self, resp: dict) -> None:
        acked = resp.get("acknowledged", False)
        ts = time.strftime("%H:%M:%S", time.gmtime(resp.get("received_at", 0)))

        if acked:
            self._status_icon.setStyleSheet(f"color: {C.GREEN}; font-size: 14px;")
            self._status_text.setText("ACKNOWLEDGED")
            self._status_text.setStyleSheet(f"color: {C.GREEN}; font-weight: bold;")
        else:
            self._status_icon.setStyleSheet(f"color: {C.RED}; font-size: 14px;")
            self._status_text.setText("REJECTED")

        detail = QLabel(f"Received from local device\n{ts}")
        detail.setProperty("dim", True)
        self.layout().insertWidget(4, detail)

        self._btn_cancel.hide()
        self._btn_close.show()

        self.acknowledged.emit(self._request_id)

    def getRequest(self) -> dict:
        return {
            "request_id": self._request_id,
            "reason": f"Trip {self._trip.trip_id} may miss DELIVER_BY",
            "subject_ref": self._trip.driver_id,
            "severity": "HIGH" if self._trip.state.value == "CRITICAL" else "INFO",
            "source_adapter": "lan",
        }

    def getRequestID(self) -> str:
        return self._request_id
