"""GUI tests. Unit tests for trip_model/icons always run. Widget smoke tests require display."""
from __future__ import annotations

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Unit tests (no display needed)
# ---------------------------------------------------------------------------

from otp.gui.trip_model import (
    TripItem, TripState, STATE_LABELS, STATE_ACTIONS,
    compute_state, trip_fromRoadStar_dispatch, _format_time, _format_delta,
)
from otp.gui.icons import state_color


def test_state_computation_acknowledged():
    t = TripItem("1", "D1", "A1", ack_status="acknowledged")
    assert compute_state(t) is TripState.RESOLVED

def test_state_computation_waiting():
    t = TripItem("1", "D1", "A1", delta_minutes=27, ack_status="waiting")
    assert compute_state(t) is TripState.WAITING_ACK

def test_state_computation_critical():
    t = TripItem("1", "D1", "A1", delta_minutes=27, ack_status="none")
    assert compute_state(t) is TripState.CRITICAL

def test_state_computation_at_risk_negative():
    t = TripItem("1", "D1", "A1", delta_minutes=-10, ack_status="none")
    assert compute_state(t) is TripState.AT_RISK

def test_state_computation_on_time():
    t = TripItem("1", "D1", "A1", delta_minutes=-60, ack_status="none")
    assert compute_state(t) is TripState.ON_TIME

def test_state_computation_unknown():
    t = TripItem("1", "D1", "A1", delta_minutes=None)
    assert compute_state(t) is TripState.UNKNOWN

def test_format_time():
    assert _format_time("2026-09-10T14:32:00Z") == "14:32"
    assert _format_time(None) == "\u2014"
    assert _format_time("") == "\u2014"

def test_format_delta():
    assert _format_delta(27) == "+27m"
    assert _format_delta(-10) == "-10m"
    assert _format_delta(0) == "0m"
    assert _format_delta(None) == "\u2014"

def test_state_labels():
    assert STATE_LABELS[TripState.CRITICAL] == "CRITICAL"
    assert STATE_LABELS[TripState.RESOLVED] == "RESOLVED"
    assert STATE_LABELS[TripState.WAITING_ACK] == "WAITING ACK"

def test_state_actions():
    assert STATE_ACTIONS[TripState.CRITICAL] == "ACK NOW"
    assert STATE_ACTIONS[TripState.RESOLVED] == "\u2713 DONE"

def test_trip_from_dispatch_normalized():
    row = {
        "trip_ref": "28471", "driver_id": "5042", "leg_ref": "L1",
        "expected_at": "2026-09-10T14:32:00Z", "due_at": "2026-09-10T14:05:00Z",
        "operation_status": "IN_TRANSIT",
    }
    t = trip_fromRoadStar_dispatch(row)
    assert t.trip_id == "28471"
    assert t.driver_id == "5042"
    assert t.delta_minutes == 27

def test_trip_from_dispatch_raw_roadstar():
    row = {
        "TRIP_NUMBER": "18422", "DRIVER_ID": "1881", "LS_LEG_ID": "L2",
        "LS_EXPECTED_DATE": "2026-09-10T15:10:00Z", "DELIVER_BY": "2026-09-10T15:00:00Z",
        "STATUS": "DISP",
    }
    t = trip_fromRoadStar_dispatch(row)
    assert t.trip_id == "18422"
    assert t.driver_id == "1881"
    assert t.delta_minutes == 10

def test_state_color_values():
    assert state_color("CRITICAL") == "#da3633"
    assert state_color("RESOLVED") == "#3fb950"
    assert state_color("UNKNOWN") == "#8b949e"

def test_trip_item_fields():
    t = TripItem(
        trip_id="28471", driver_id="5042", assignment_id="A1",
        eta="2026-09-10T14:32:00Z", deliver_by="2026-09-10T14:05:00Z",
        delta_minutes=27, state=TripState.CRITICAL,
        finding_code="ETA_THRESHOLD_EXCEEDED", finding_message="ETA > due",
        remaining_hos=0.0, operation_status="IN_TRANSIT",
    )
    assert t.trip_id == "28471"
    assert t.remaining_hos == 0.0
    assert t.finding_code == "ETA_THRESHOLD_EXCEEDED"


# ---------------------------------------------------------------------------
# Widget smoke tests (require display server)
# ---------------------------------------------------------------------------

HAS_DISPLAY = sys.platform == "win32" or os.environ.get("DISPLAY") is not None

pytestmark_display = pytest.mark.skipif(not HAS_DISPLAY, reason="No display server")


@pytestmark_display
class TestWidgetSmoke:
    def _app(self):
        from PySide6.QtWidgets import QApplication
        from otp.gui.styles import apply_dark_theme
        a = QApplication.instance()
        if a is None:
            import sys
            a = QApplication(sys.argv)
            apply_dark_theme(a)
        return a

    def test_main_window(self):
        self._app()
        from otp.gui.main_window import MainWindow
        w = MainWindow()
        assert w.windowTitle() == "Operational Trust Pipeline"
        w.close()

    def test_trip_table(self):
        self._app()
        from otp.gui.trip_table import TripTable
        t = TripTable()
        assert t._model.columnCount() == 8

    def test_detail_panel_clear(self):
        self._app()
        from otp.gui.detail_panel import DetailPanel
        d = DetailPanel()
        d.setTrip(None)
        assert "No trip selected" in d._header.text()

    def test_detail_panel_with_trip(self):
        self._app()
        from otp.gui.detail_panel import DetailPanel
        d = DetailPanel()
        t = TripItem("28471", "5042", "A1", state=TripState.CRITICAL,
                      finding_code="ETA_THRESHOLD_EXCEEDED", finding_message="ETA > due")
        d.setTrip(t)
        assert "28471" in d._header.text()

    def test_lan_modal(self):
        self._app()
        from otp.gui.lan_modal import LanModal
        t = TripItem("28471", "5042", "A1", state=TripState.CRITICAL)
        m = LanModal(t, "http://127.0.0.1:8787", "test-token")
        assert m.windowTitle() == "Request Acknowledgement"
        m.close()
