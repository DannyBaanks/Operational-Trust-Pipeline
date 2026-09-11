"""Colored dot icons for trip states. Text is always the primary indicator."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from .styles import C
from ..gui import trip_model as _tm  # deferred to avoid circular


_STATE_COLORS = {
    "CRITICAL": C.RED,
    "AT_RISK": C.ORANGE,
    "WAITING_ACK": C.ORANGE,
    "DELIVERY_UNCERTAIN": C.GRAY,
    "ON_TIME": C.TEXT_DIM,
    "RESOLVED": C.GREEN,
    "BLOCKED": C.GRAY,
    "UNKNOWN": C.GRAY,
}


def state_color(state_name: str) -> str:
    return _STATE_COLORS.get(state_name, C.GRAY)


def state_icon(state_name: str) -> QIcon:
    """12x12 colored square icon for a trip state."""
    color = QColor(state_color(state_name))
    pixmap = QPixmap(12, 12)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 12, 12, 2, 2)
    painter.end()
    return QIcon(pixmap)
