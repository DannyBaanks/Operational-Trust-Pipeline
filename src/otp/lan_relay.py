"""Minimal local-network relay for the OTP LAN demo.

No discovery. No voice. No push. No arbitrary code execution.
A request arrives via POST, a human sees it on a web page, taps ACK or REJECT,
and the response is returned via polling.

Security:
- Session token (UUID4) generated per relay start, required on all endpoints
- No filesystem authority (in-memory stores only)
- No shell. No arbitrary code. No device enumeration.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any

from flask import Flask, request as flask_request, jsonify, render_template

# In-memory stores. Valid only for the lifetime of the relay process.
_pending: list[dict[str, Any]] = []
_responses: dict[str, dict[str, Any]] = {}
_store_lock = threading.Lock()

_session_token: str = ""


def _auth_ok() -> bool:
    token = flask_request.headers.get("X-Session-Token", "")
    return token == _session_token


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    @app.route("/receiver", methods=["GET"])
    def receiver_page():
        return render_template("lan_receiver.html")

    @app.route("/dispatch", methods=["GET"])
    def dispatch_page():
        return render_template("dispatch_map.html")

    @app.route("/api/scenario", methods=["GET"])
    def scenario():
        if not _auth_ok():
            return jsonify({"error": "unauthorized"}), 401
        from .roadstar_simulator import RoadStarSimulator
        samples = [item.as_dict() for item in RoadStarSimulator().stream()]
        return jsonify({"ok": True, "samples": samples})

    @app.route("/api/geofence", methods=["GET"])
    def geofence():
        if not _auth_ok():
            return jsonify({"error": "unauthorized"}), 401
        from .roadstar_simulator import LONDON_FACILITY
        return jsonify({"ok": True, "geofence": {
            "facility_id": LONDON_FACILITY.facility_id,
            "name": LONDON_FACILITY.name,
            "latitude": LONDON_FACILITY.latitude,
            "longitude": LONDON_FACILITY.longitude,
            "radius_km": LONDON_FACILITY.radius_km,
        }})

    @app.route("/api/poll", methods=["GET"])
    def poll():
        if not _auth_ok():
            return jsonify({"error": "unauthorized"}), 401
        with _store_lock:
            if _pending:
                item = _pending.pop(0)
                return jsonify({"ok": True, "request": item})
        return jsonify({"ok": False})

    @app.route("/api/inject", methods=["POST"])
    def inject():
        if not _auth_ok():
            return jsonify({"error": "unauthorized"}), 401
        body = flask_request.get_json(force=True)
        with _store_lock:
            _pending.append(body)
        return jsonify({"ok": True})

    @app.route("/api/respond", methods=["POST"])
    def respond():
        if not _auth_ok():
            return jsonify({"error": "unauthorized"}), 401
        body = flask_request.get_json(force=True)
        request_id = body.get("request_id")
        if not request_id:
            return jsonify({"error": "missing request_id"}), 400
        with _store_lock:
            # Duty actions (ACCEPT/ARRIVED/DEPARTED/...) are relay-level labels.
            # They resolve to ACK/REJECT semantics so the OTP lease pipeline
            # stays unchanged: acknowledged=True satisfies, False does not.
            _responses[request_id] = {
                "request_id": request_id,
                "acknowledged": body.get("acknowledged", False),
                "action": body.get("action", "ACK" if body.get("acknowledged", False) else "REJECT"),
                "message": body.get("message", ""),
                "received_at": time.time(),
            }
        return jsonify({"ok": True})

    @app.route("/api/status/<request_id>", methods=["GET"])
    def status(request_id: str):
        if not _auth_ok():
            return jsonify({"error": "unauthorized"}), 401
        with _store_lock:
            resp = _responses.pop(request_id, None)
        if resp:
            return jsonify({"ok": True, "responded": True, "response": resp})
        return jsonify({"ok": True, "responded": False})

    return app


def inject_request(request_id: str, payload: dict[str, Any]) -> None:
    """Called by the adapter to stage a request for the web page."""
    with _store_lock:
        _pending.append({"request_id": request_id, "payload": payload})


def get_response(request_id: str) -> dict[str, Any] | None:
    """Called by the adapter to retrieve the human's response."""
    with _store_lock:
        return _responses.pop(request_id, None)


def start_relay(host: str = "0.0.0.0", port: int = 8787) -> tuple[str, int, str]:
    """Start the Flask relay in a daemon thread. Returns (host, port, token)."""
    global _session_token
    _session_token = str(uuid.uuid4())
    app = create_app()
    thread = threading.Thread(target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False), daemon=True)
    thread.start()
    time.sleep(0.3)  # let the server bind
    return host, port, _session_token
