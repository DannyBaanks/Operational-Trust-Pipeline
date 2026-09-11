from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import plain, sha256


COMPONENTS = ("event", "lease", "finding", "action", "result")

def make_receipt(run: dict[str, Any], previous_receipt_sha256: str | None = None) -> dict[str, Any]:
    components = {name: plain(run[name]) if run.get(name) is not None else None for name in COMPONENTS}
    hashes = {name: sha256(value) for name, value in components.items()}
    receipt = {"schema_version": "evidence-receipt/1", "execution_id": run["execution_id"], "source_adapter": run["source_adapter"],
               "policy_version": run["policy_version"], "channel_adapter": run["channel_adapter"], "verdict": plain(run["verdict"]),
               "components": components, "component_sha256": hashes, "previous_receipt_sha256": previous_receipt_sha256,
               "limitations": ["Integrity verification does not replay external provider behavior.", "An unanchored append-only chain cannot detect tail truncation."]}
    receipt["receipt_sha256"] = sha256(receipt)
    return receipt

def verify_receipt(receipt: dict[str, Any]) -> tuple[bool, str]:
    body = dict(receipt); claimed = body.pop("receipt_sha256", None)
    if claimed != sha256(body): return False, "receipt hash mismatch"
    for name, value in receipt["components"].items():
        if receipt["component_sha256"].get(name) != sha256(value): return False, f"component hash mismatch: {name}"
    return True, "PASS"

def append_ledger(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = None
    if path.exists() and path.stat().st_size:
        prior = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])["receipt_sha256"]
    chained = make_receipt({"execution_id": receipt["execution_id"], "source_adapter": receipt["source_adapter"], "policy_version": receipt["policy_version"], "channel_adapter": receipt["channel_adapter"], "verdict": receipt["verdict"], **receipt["components"]}, prior)
    path.open("a", encoding="utf-8").write(json.dumps(chained, sort_keys=True) + "\n")

def verify_ledger(path: Path) -> tuple[bool, str]:
    previous = None
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        receipt = json.loads(line); ok, reason = verify_receipt(receipt)
        if not ok: return False, f"line {index + 1}: {reason}"
        if receipt["previous_receipt_sha256"] != previous: return False, f"line {index + 1}: chain mismatch"
        previous = receipt["receipt_sha256"]
    return True, "PASS"
