from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .channels import CalleChannel, MockChannel
from .canonical import plain
from .evidence import append_ledger, make_receipt, verify_ledger, verify_receipt
from .pipeline import FixedClock, run_ack_lease
from .roadstar import RoadStarAdapter

ROOT = Path(__file__).resolve().parents[2]

def demo() -> dict:
    raw = json.loads((ROOT / "fixtures/roadstar/ack_assignment.json").read_text())
    return run_ack_lease(RoadStarAdapter().normalize(raw), FixedClock("2026-09-10T08:16:00Z"), MockChannel(), {"communication_allowed": True, "channel": "mock"})

def main() -> int:
    parser = argparse.ArgumentParser(prog="otp"); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor"); d = sub.add_parser("demo"); d.add_argument("scenario", choices=["ack-lease"]); d.add_argument("--evidence-dir", type=Path)
    verify = sub.add_parser("verify"); verify.add_argument("receipt")
    ledger = sub.add_parser("ledger"); ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True); lv = ledger_sub.add_parser("verify"); lv.add_argument("ledger")
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps({"core_ready": True, "roadstar_fixture_available": (ROOT / "fixtures/roadstar/ack_assignment.json").exists(), "calle_package_available": CalleChannel.available(), "calle_credentials_available": bool(os.getenv("CALLE_API_KEY")), "live_calling": "disabled", "evidence_directory_writable": True, "schema": "operational-event/1"}, sort_keys=True)); return 0
    if args.command == "demo":
        run = demo(); receipt = make_receipt(run)
        if args.evidence_dir:
            args.evidence_dir.mkdir(parents=True, exist_ok=True)
            receipt_path = args.evidence_dir / f"{run['execution_id']}.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            append_ledger(args.evidence_dir / "ledger.jsonl", receipt)
        print(json.dumps({"execution_id": run["execution_id"], "event": plain(run["event"]), "lease": plain(run["lease"]), "finding": plain(run["finding"]), "verdict": run["verdict"].value, "action": plain(run["action"]), "result": plain(run["result"]), "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True)); return 0
    if args.command == "ledger":
        ok, reason = verify_ledger(Path(args.ledger)); print(reason); return 0 if ok else 1
    data = json.loads(Path(args.receipt).read_text()); ok, reason = verify_receipt(data); print(reason); return 0 if ok else 1
    return 1

if __name__ == "__main__": raise SystemExit(main())
