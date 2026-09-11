"""Detail panel: WHY THIS FIRED / ACTION / STATUS / EVIDENCE."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from .styles import C, FONTS
from .trip_model import TripItem, TripState, STATE_LABELS


def _label(text: str, dim: bool = False, heading: bool = False) -> QLabel:
    lbl = QLabel(text)
    if dim:
        lbl.setProperty("dim", True)
    if heading:
        lbl.setProperty("heading", True)
    return lbl


def _value(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONTS["mono"], 11))
    return lbl


def _card() -> QFrame:
    frame = QFrame()
    frame.setProperty("class", "card")
    frame.setObjectName("card")
    return frame


class DetailPanel(QWidget):
    requestAck = Signal()
    markReviewed = Signal()
    viewEvidence = Signal()
    copyHash = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._trip: TripItem | None = None
        self._build_ui()
        self._clear()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Trip header
        self._header = QLabel("")
        self._header.setFont(QFont(FONTS["sans"], 12, QFont.Weight.Bold))
        layout.addWidget(self._header)

        # Three-column row: WHY / ACTION / STATUS
        row = QHBoxLayout()
        row.setSpacing(8)

        # WHY THIS FIRED
        why_card = _card()
        why_layout = QVBoxLayout(why_card)
        why_layout.setContentsMargins(12, 8, 12, 8)
        why_layout.setSpacing(4)
        why_layout.addWidget(_label("WHY THIS FIRED", heading=True))
        self._eta = _value("\u2014")
        self._due = _value("\u2014")
        self._delta = _value("\u2014")
        self._finding_label = _value("\u2014")
        self._finding_msg = _label("", dim=True)
        self._hos = _label("")
        self._hos.setProperty("dim", True)
        for lbl, val in [("ETA", self._eta), ("DELIVER_BY", self._due), ("DELTA", self._delta)]:
            r = QHBoxLayout()
            r.addWidget(_label(lbl, dim=True))
            r.addStretch()
            r.addWidget(val)
            why_layout.addLayout(r)
        why_layout.addSpacing(4)
        why_layout.addWidget(self._finding_label)
        why_layout.addWidget(self._finding_msg)
        why_layout.addWidget(self._hos)
        why_layout.addStretch()
        row.addWidget(why_card, 2)

        # ACTION
        action_card = _card()
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(12, 8, 12, 8)
        action_layout.setSpacing(4)
        action_layout.addWidget(_label("ACTION", heading=True))
        self._action_desc = _label("")
        action_layout.addWidget(self._action_desc)
        self._channel_label = _label("")
        self._channel_label.setProperty("dim", True)
        action_layout.addWidget(self._channel_label)
        action_layout.addSpacing(8)
        self._btn_ack = QPushButton("Request ACK")
        self._btn_ack.setObjectName("primary")
        self._btn_ack.clicked.connect(self.requestAck.emit)
        self._btn_review = QPushButton("Mark Reviewed")
        self._btn_review.clicked.connect(self.markReviewed.emit)
        self._btn_review.hide()
        action_layout.addWidget(self._btn_ack)
        action_layout.addWidget(self._btn_review)
        action_layout.addStretch()
        row.addWidget(action_card, 2)

        # STATUS
        status_card = _card()
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(4)
        status_layout.addWidget(_label("STATUS", heading=True))
        self._status_dot = _value("\u2022")
        self._status_label = _value("\u2014")
        self._attempt = _label("")
        self._attempt.setProperty("dim", True)
        self._last_sent = _label("")
        self._last_sent.setProperty("dim", True)
        self._receipt_status = _label("")
        self._receipt_status.setProperty("dim", True)
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label)
        status_layout.addSpacing(4)
        status_layout.addWidget(self._attempt)
        status_layout.addWidget(self._last_sent)
        status_layout.addWidget(self._receipt_status)
        status_layout.addStretch()
        row.addWidget(status_card, 2)

        layout.addLayout(row)

        # EVIDENCE
        ev_card = _card()
        ev_layout = QHBoxLayout(ev_card)
        ev_layout.setContentsMargins(12, 8, 12, 8)
        ev_layout.setSpacing(8)
        ev_layout.addWidget(_label("EVIDENCE", heading=True))
        self._receipt_hash = _value("\u2014")
        ev_layout.addWidget(self._receipt_hash)
        self._verified = _label("")
        self._verified.setProperty("dim", True)
        ev_layout.addWidget(self._verified)
        ev_layout.addStretch()
        self._btn_view = QPushButton("View JSON")
        self._btn_view.clicked.connect(self.viewEvidence.emit)
        self._btn_copy = QPushButton("Copy Hash")
        self._btn_copy.clicked.connect(self.copyHash.emit)
        ev_layout.addWidget(self._btn_view)
        ev_layout.addWidget(self._btn_copy)
        layout.addWidget(ev_card)

    def _clear(self) -> None:
        self._header.setText("No trip selected")
        self._eta.setText("\u2014")
        self._due.setText("\u2014")
        self._delta.setText("\u2014")
        self._finding_label.setText("")
        self._finding_msg.setText("")
        self._hos.setText("")
        self._action_desc.setText("Select a trip from the table")
        self._channel_label.setText("")
        self._status_dot.setText("")
        self._status_label.setText("\u2014")
        self._attempt.setText("")
        self._last_sent.setText("")
        self._receipt_status.setText("")
        self._receipt_hash.setText("\u2014")
        self._verified.setText("")
        self._btn_ack.hide()
        self._btn_review.hide()

    def setTrip(self, trip: TripItem | None) -> None:
        self._trip = trip
        if trip is None:
            self._clear()
            return
        self._update()

    def _update(self) -> None:
        t = self._trip
        if t is None:
            return

        from .trip_model import _format_time, _format_delta
        self._header.setText(f"Trip {t.trip_id} \u2014 Driver {t.driver_id}")
        self._eta.setText(_format_time(t.eta))
        self._due.setText(_format_time(t.deliver_by))
        self._delta.setText(_format_delta(t.delta_minutes))

        # Delta color
        if t.delta_minutes is not None and t.delta_minutes > 0:
            self._delta.setStyleSheet(f"color: {C.RED}; font-weight: bold;")
        elif t.delta_minutes is not None and t.delta_minutes > -30:
            self._delta.setStyleSheet(f"color: {C.ORANGE};")
        else:
            self._delta.setStyleSheet("")

        self._finding_label.setText(t.finding_code or "\u2014")
        self._finding_msg.setText(t.finding_message)

        if t.remaining_hos is not None:
            self._hos.setText(f"Driver remaining hours: {t.remaining_hos}")
        else:
            self._hos.setText("")

        # Action
        needs_ack = t.state in (TripState.CRITICAL, TripState.AT_RISK, TripState.WAITING_ACK, TripState.UNKNOWN)
        self._btn_ack.setVisible(needs_ack and t.ack_status != "acknowledged")
        self._btn_review.setVisible(needs_ack and t.ack_status != "acknowledged")

        if t.ack_status == "acknowledged":
            self._action_desc.setText("Acknowledgement received")
        elif t.state == TripState.CRITICAL:
            self._action_desc.setText("Human acknowledgement required")
        elif t.state == TripState.AT_RISK:
            self._action_desc.setText("Monitor \u2014 approaching deadline")
        elif t.state == TripState.ON_TIME:
            self._action_desc.setText("No action required")
        else:
            self._action_desc.setText("Select action")

        self._channel_label.setText(f"Channel: {t.channel_status}")

        # Status
        state_label = STATE_LABELS.get(t.state, t.state.value)
        self._status_dot.setText("\u25cf")
        color = {
            TripState.CRITICAL: C.RED,
            TripState.AT_RISK: C.ORANGE,
            TripState.WAITING_ACK: C.ORANGE,
            TripState.RESOLVED: C.GREEN,
        }.get(t.state, C.GRAY)
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._status_label.setText(state_label)

        if t.last_attempt:
            self._last_sent.setText(f"Last attempt: {t.last_attempt}")
        else:
            self._last_sent.setText("No attempts")

        if t.receipt_hash:
            short = t.receipt_hash[:8] + "\u2026" + t.receipt_hash[-4:]
            self._receipt_hash.setText(short)
            if t.receipt_verified:
                self._verified.setText("\u2713 VERIFIED")
                self._verified.setStyleSheet(f"color: {C.GREEN}; font-weight: bold;")
            else:
                self._verified.setText("")
            self._receipt_status.setText(f"Receipt: {short}")
        else:
            self._receipt_hash.setText("\u2014")
            self._verified.setText("")
            self._receipt_status.setText("Receipt: pending")

    def getReceiptHash(self) -> str | None:
        if self._trip and self._trip.receipt_hash:
            return self._trip.receipt_hash
        return None
