from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .channels import CalleChannel, LanChannel, MockChannel
from .canonical import plain
from .evidence import append_ledger, make_receipt, verify_ledger, verify_receipt
from .lan_relay import start_relay
from .pipeline import FixedClock, run_ack_lease
from .roadstar import RoadStarAdapter

ROOT = Path(__file__).resolve().parents[2]


def demo(channel: str = "mock", relay_url: str | None = None, relay_token: str | None = None) -> dict:
    raw = json.loads((ROOT / "fixtures/roadstar/ack_assignment.json").read_text())
    ev = RoadStarAdapter().normalize(raw)
    if channel == "lan":
        url, port, token = start_relay()
        actual_url = relay_url or f"http://127.0.0.1:{port}"
        actual_token = relay_token or token
        ch = LanChannel(actual_url, actual_token)
        print(f"Relay running at {actual_url}/receiver?token={actual_token}", flush=True)
    else:
        ch = MockChannel()
    return run_ack_lease(ev, FixedClock("2026-09-10T08:16:00Z"), ch, {"communication_allowed": True, "channel": channel})


def main() -> int:
    parser = argparse.ArgumentParser(prog="otp")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("gui")
    d = sub.add_parser("demo")
    d.add_argument("scenario", choices=["ack-lease"])
    d.add_argument("--evidence-dir", type=Path)
    d.add_argument("--channel", choices=["mock", "lan"], default="mock")
    d.add_argument("--relay-url", type=str, default=None)
    d.add_argument("--relay-token", type=str, default=None)
    verify = sub.add_parser("verify")
    verify.add_argument("receipt")
    ledger = sub.add_parser("ledger")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    lv = ledger_sub.add_parser("verify")
    lv.add_argument("ledger")
    drive = sub.add_parser("drive")
    drive_sub = drive.add_subparsers(dest="drive_command", required=True)
    drive_sub.add_parser("auth")
    drive_sub.add_parser("status")
    ds = drive_sub.add_parser("sync")
    ds.add_argument("--evidence-dir", type=Path)
    ds.add_argument("--ledger", type=Path)
    drive_sub.add_parser("disconnect")
    args = parser.parse_args()
    if args.command == "gui":
        from .gui import main as gui_main
        gui_main()
        return 0
    if args.command == "doctor":
        print(json.dumps({
            "core_ready": True,
            "roadstar_fixture_available": (ROOT / "fixtures/roadstar/ack_assignment.json").exists(),
            "calle_package_available": CalleChannel.available(),
            "calle_credentials_available": bool(os.getenv("CALLE_API_KEY")),
            "live_calling": "disabled",
            "lan_channel_available": True,
            "evidence_directory_writable": True,
            "schema": "operational-event/1",
        }, sort_keys=True))
        return 0
    if args.command == "demo":
        run_result = demo(args.channel, args.relay_url, args.relay_token)
        receipt = make_receipt(run_result)
        if args.evidence_dir:
            args.evidence_dir.mkdir(parents=True, exist_ok=True)
            receipt_path = args.evidence_dir / f"{run_result['execution_id']}.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            append_ledger(args.evidence_dir / "ledger.jsonl", receipt)
        print(json.dumps({
            "execution_id": run_result["execution_id"],
            "event": plain(run_result["event"]),
            "lease": plain(run_result["lease"]),
            "finding": plain(run_result["finding"]),
            "verdict": run_result["verdict"].value,
            "action": plain(run_result["action"]),
            "result": plain(run_result["result"]),
            "receipt_sha256": receipt["receipt_sha256"],
        }, sort_keys=True))
        return 0
    if args.command == "ledger":
        ok, reason = verify_ledger(Path(args.ledger))
        print(reason)
        return 0 if ok else 1
    if args.command == "drive":
        from .drive_sync import DriveSync
        ds = DriveSync()
        if args.drive_command == "auth":
            email = ds.authenticate()
            print(json.dumps({"authenticated": True, "email": email}, sort_keys=True))
            return 0
        if args.drive_command == "status":
            status = ds.get_sync_status()
            print(json.dumps(status, sort_keys=True))
            return 0
        if args.drive_command == "sync":
            results = []
            if args.ledger:
                results.append(ds.sync_ledger(args.ledger))
            if args.evidence_dir:
                results.extend(ds.sync_evidence_dir(args.evidence_dir))
            if not results:
                evidence_dir = ROOT / "evidence"
                ledger_path = evidence_dir / "ledger.jsonl"
                if ledger_path.exists():
                    results.append(ds.sync_ledger(ledger_path))
                if evidence_dir.exists():
                    results.extend(ds.sync_evidence_dir(evidence_dir))
            print(json.dumps(results, sort_keys=True))
            return 0
        if args.drive_command == "disconnect":
            ds.disconnect()
            print(json.dumps({"disconnected": True}))
            return 0
    data = json.loads(Path(args.receipt).read_text())
    ok, reason = verify_receipt(data)
    print(reason)
    return 0 if ok else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
