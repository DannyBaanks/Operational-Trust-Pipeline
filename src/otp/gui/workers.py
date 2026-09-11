"""Background workers for pipeline execution and LAN relay."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from ..channels import MockChannel
from ..pipeline import AckLeasePolicy, DeliveryTimingPolicy, HosCapacityPolicy, FixedClock, run_ack_lease
from ..roadstar import RoadStarAdapter
from ..evidence import make_receipt
from ..canonical import sha256

ROOT = Path(__file__).resolve().parents[2]


class TripLoaderWorker(QThread):
    """Load RoadStar workbook, run policies, emit list of TripItem dicts."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def run(self) -> None:
        try:
            adapter = RoadStarAdapter()
            workbook = ROOT / "fixtures" / "roadstar" / "Hackathon_Data.xlsx"
            if not workbook.exists():
                self.error.emit(f"Workbook not found: {workbook}")
                return

            # Load driver HOS data
            driver_hos: dict[str, float] = {}
            for row in adapter.driver_rows(workbook):
                did = str(row.get("DRIVER_ID", ""))
                rh = row.get("REMAINING_HOURS")
                if did and isinstance(rh, (int, float)):
                    driver_hos[did] = rh

            # Load dispatch rows
            from .trip_model import TripItem, TripState, trip_fromRoadStar_dispatch, compute_state
            trips: list[TripItem] = []
            for row in adapter.dispatch_rows(workbook):
                trip = trip_fromRoadStar_dispatch(row, driver_hos)

                # Run policies on normalized event
                ev = adapter.normalize(row)
                policy_ack = AckLeasePolicy()
                policy_timing = DeliveryTimingPolicy()
                policy_hos = HosCapacityPolicy()

                # Delivery timing finding
                timing_finding = policy_timing.evaluate(ev)
                trip.finding_code = timing_finding.reason_code
                trip.finding_message = timing_finding.reason
                trip.finding_severity = timing_finding.severity

                # HOS finding (override if worse)
                hos_finding = policy_hos.evaluate(ev)
                if hos_finding.severity == "HIGH" and trip.finding_severity != "HIGH":
                    trip.finding_code = hos_finding.reason_code
                    trip.finding_message = hos_finding.reason
                    trip.finding_severity = hos_finding.severity

                trip.state = compute_state(trip)
                trips.append(trip)

            self.finished.emit(trips)
        except Exception as e:
            self.error.emit(str(e))


class LanRelayWorker(QThread):
    """Start relay, poll for human response."""
    url_ready = Signal(str)
    response = Signal(dict)
    error = Signal(str)

    def __init__(self, relay_url: str, token: str, request_id: str, timeout: float = 300.0, parent=None) -> None:
        super().__init__(parent)
        self.relay_url = relay_url
        self.token = token
        self.request_id = request_id
        self.timeout = timeout
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        import urllib.request
        import urllib.error

        deadline = time.time() + self.timeout
        while time.time() < deadline and not self._cancelled:
            try:
                req = urllib.request.Request(
                    f"{self.relay_url}/api/status/{self.request_id}",
                    headers={"X-Session-Token": self.token},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    if data.get("responded"):
                        self.response.emit(data["response"])
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(2.0)

        if not self._cancelled:
            self.error.emit("HUMAN_TIMEOUT")
