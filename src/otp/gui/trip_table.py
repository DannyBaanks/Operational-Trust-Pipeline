"""Sortable QTableView for trip list."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableView

from .styles import C
from .icons import state_color
from .trip_model import TripItem, TripState, STATE_LABELS, STATE_ACTIONS, STATE_SEVERITY


_COLUMNS = [
    ("trip_id", "ID"),
    ("driver_id", "DRIVER"),
    ("_eta", "ETA"),
    ("_deliver_by", "DUE"),
    ("_delta", "DELTA"),
    ("_state_label", "STATE"),
    ("_action", "ACTION"),
    ("_ack", "ACK"),
]


class TripTableModel(QAbstractTableModel):
    def __init__(self, trips: list[TripItem] | None = None) -> None:
        super().__init__()
        self._trips: list[TripItem] = trips or []
        self._sort_column = 4  # delta
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._sort()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._trips)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        trip = self._trips[index.row()]
        key = _COLUMNS[index.column()][0]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(trip, key)

        if role == Qt.ItemDataRole.ForegroundRole:
            if key == "_state_label":
                return QColor(state_color(trip.state.value))
            if key == "_delta" and trip.delta_minutes is not None and trip.delta_minutes > 0:
                return QColor(C.RED)
            if key == "_action":
                if trip.state == TripState.CRITICAL:
                    return QColor(C.ORANGE)
                if trip.state == TripState.RESOLVED:
                    return QColor(C.GREEN)

        if role == Qt.ItemDataRole.FontRole:
            if key in ("trip_id", "_state_label"):
                from PySide6.QtGui import QFont
                f = QFont("Consolas", 11)
                f.setBold(True)
                return f

        if role == Qt.ItemDataRole.UserRole:
            return trip

        return None

    def _display(self, trip: TripItem, key: str) -> str:
        if key == "trip_id":
            return trip.trip_id
        if key == "driver_id":
            return trip.driver_id
        if key == "_eta":
            from .trip_model import _format_time
            return _format_time(trip.eta)
        if key == "_deliver_by":
            from .trip_model import _format_time
            return _format_time(trip.deliver_by)
        if key == "_delta":
            from .trip_model import _format_delta
            return _format_delta(trip.delta_minutes)
        if key == "_state_label":
            return STATE_LABELS.get(trip.state, trip.state.value)
        if key == "_action":
            return STATE_ACTIONS.get(trip.state, "")
        if key == "_ack":
            return trip.ack_status.capitalize() if trip.ack_status != "none" else "\u2014"
        return ""

    def _sort(self) -> None:
        key = _COLUMNS[self._sort_column][0]
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder

        def sort_key(t: TripItem):
            if key == "_delta":
                return t.delta_minutes if t.delta_minutes is not None else 999999
            if key == "_state_label":
                return STATE_SEVERITY.get(t.state, 99)
            if key == "_eta":
                from .trip_model import _parse_time
                return _parse_time(t.eta) or ""
            if key == "_deliver_by":
                from .trip_model import _parse_time
                return _parse_time(t.deliver_by) or ""
            if key == "_ack":
                return {"acknowledged": 0, "waiting": 1, "rejected": 2, "none": 3}.get(t.ack_status, 4)
            val = getattr(t, key, "")
            return val if val is not None else ""

        self._trips.sort(key=sort_key, reverse=reverse)

    def setTrips(self, trips: list[TripItem]) -> None:
        self.beginResetModel()
        self._trips = list(trips)
        self._sort()
        self.endResetModel()

    def tripAt(self, row: int) -> TripItem | None:
        if 0 <= row < len(self._trips):
            return self._trips[row]
        return None

    def tripFromIndex(self, index: QModelIndex) -> TripItem | None:
        if index.isValid():
            return self._trips[index.row()]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        self._sort_column = column
        self._sort_order = order
        self._sort()
        self.layoutChanged.emit()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return _COLUMNS[section][1]
        return None


class TripTable(QTableView):
    tripSelected = Signal(object)  # TripItem or None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = TripTableModel()
        self.setModel(self._model)
        self._setup()

    def _setup(self) -> None:
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().resizeSection(2, 60)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().resizeSection(3, 60)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().resizeSection(4, 60)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().resizeSection(5, 140)
        self.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().resizeSection(6, 80)
        self.setSortingEnabled(True)
        self.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        self.selectionModel().selectionChanged.connect(self._on_select)
        self.setFixedHeight(200)

    def setTrips(self, trips: list[TripItem]) -> None:
        self._model.setTrips(trips)

    def selectedTrip(self) -> TripItem | None:
        indexes = self.selectionModel().selectedRows()
        if indexes:
            return self._model.tripFromIndex(indexes[0])
        return None

    def _on_select(self) -> None:
        self.tripSelected.emit(self.selectedTrip())
