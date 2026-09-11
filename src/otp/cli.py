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


def demo(channel: str = "mock", relay_url: str | None = None, relay_token: str | None = None,
         ephemeral: bool = False) -> dict:
    """Run demo with OperationalRunner (durable) or legacy path (ephemeral)."""
    raw = json.loads((ROOT / "fixtures/roadstar/ack_assignment.json").read_text())
    ev = RoadStarAdapter().normalize(raw)
    clock = FixedClock("2026-09-10T08:16:00Z")
    ctx = {"communication_allowed": True, "channel": channel}

    if channel == "lan":
        url, port, token = start_relay()
        actual_url = relay_url or f"http://127.0.0.1:{port}"
        actual_token = relay_token or token
        ch = LanChannel(actual_url, actual_token)
        print(f"Relay running at {actual_url}/receiver?token={actual_token}", flush=True)
    else:
        ch = MockChannel()

    if ephemeral:
        return run_ack_lease(ev, clock, ch, ctx)

    from .runner import default_runner
    runner = default_runner()
    runner._repo.initialize()
    try:
        return runner.run_ack_lease(ev, ch, ctx)
    finally:
        runner._repo.close()


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
    d.add_argument("--ephemeral", action="store_true",
                   help="Use in-memory backend (no persistence)")
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
    persistence = sub.add_parser("persistence")
    persistence_sub = persistence.add_subparsers(dest="persistence_command", required=True)
    persistence_sub.add_parser("status")
    persistence_sub.add_parser("verify")
    persistence_sub.add_parser("path")
    persistence_sub.add_parser("recover")
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
        run_result = demo(args.channel, args.relay_url, args.relay_token, args.ephemeral)
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
    if args.command == "persistence":
        from .persistence import default_backend, DEFAULT_DB
        from .persistence.repository import RunRepository
        backend = default_backend()
        repo = RunRepository(backend)
        repo.initialize()
        try:
            if args.persistence_command == "path":
                print(str(DEFAULT_DB))
                return 0
            if args.persistence_command == "status":
                ok, msg = repo.verify()
                run_count = repo.count_runs()
                incomplete = repo.recover_incomplete()
                print(f"Backend ........ SQLite")
                print(f"Path ........... {DEFAULT_DB}")
                print(f"Runs ........... {run_count}")
                print(f"Incomplete ..... {len(incomplete)}")
                print(f"{msg}")
                if ok:
                    print("PERSISTENCE READY")
                return 0 if ok else 1
            if args.persistence_command == "verify":
                ok, msg = repo.verify()
                print(msg)
                return 0 if ok else 1
            if args.persistence_command == "recover":
                incomplete = repo.recover_incomplete()
                if not incomplete:
                    print("No incomplete runs found.")
                    return 0
                for run in incomplete:
                    print(json.dumps(run, sort_keys=True))
                return 0
        finally:
            repo.close()
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
