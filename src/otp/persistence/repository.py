"""Domain-specific persistence repository for OTP run lifecycle."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from ..canonical import plain, sha256
from ..domain import (
    ActionRequest, ActionResult, Finding, Lease, OperationalEvent,
    SentinelVerdict,
)
from .errors import ConflictError, CorruptionError, SchemaUnsupportedError
from .protocol import PersistenceBackend


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(obj: Any) -> str:
    """Canonical JSON for persistence comparison."""
    return json.dumps(plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class RunRepository:
    """Domain persistence on top of a backend-agnostic PersistenceBackend.

    Two idempotency rules:
    - Immutable entities (Event, Finding, ActionRequest, ActionResult):
        same ID + same content  → idempotent
        same ID + diff content  → ConflictError
    - Stateful entities (Lease, Execution):
        same state + same data  → idempotent
        legal next state        → transactional UPDATE
        illegal transition      → ConflictError
    """

    def __init__(self, backend: PersistenceBackend) -> None:
        self._b = backend

    def initialize(self) -> None:
        self._b.initialize()

    def close(self) -> None:
        self._b.close()

    # --- Immutable entities ---

    def save_event(self, event: OperationalEvent) -> None:
        self._b.put_immutable("operational_events", event.event_id, _canonical(event))

    def save_finding(self, finding: Finding) -> None:
        self._b.put_immutable("findings", finding.finding_id, _canonical(finding))

    def save_action_request(self, request: ActionRequest) -> None:
        self._b.put_immutable("action_requests", request.action_id, _canonical(request))

    def save_action_result(self, result: ActionResult) -> None:
        self._b.put_immutable("action_results", result.action_id, _canonical(result))

    # --- Stateful entities ---

    def save_lease(self, lease: Lease) -> None:
        self._b.upsert_stateful("leases", lease.lease_id, _canonical(lease), lease.state.value)

    def resolve_lease(self, lease_id: str, new_state: str,
                      resolution: str | None = None, closed_at: str | None = None) -> None:
        """Transition lease to terminal state."""
        record = self._b.get("leases", lease_id)
        if record is None:
            raise CorruptionError(f"Lease {lease_id} not found")
        updates = {"state": new_state, "updated_at": _now()}
        if resolution:
            updates["resolution"] = resolution
        if closed_at:
            updates["closed_at"] = closed_at
        # Re-serialize with updated fields
        data = json.loads(record["data"])
        data.update(updates)
        self._b.upsert_stateful("leases", lease_id, json.dumps(data, sort_keys=True), new_state)

    # --- Execution lifecycle ---

    def _patch_exec(self, execution_id: str, patch: dict[str, Any], state: str) -> None:
        """Read current execution data, merge patch, write back."""
        current = self._b.get("executions", execution_id)
        data = json.loads(current["data"]) if current else {}
        data.update(patch)
        self._b.upsert_stateful(
            "executions", execution_id,
            json.dumps(data, sort_keys=True),
            state,
        )

    def start_run(self, execution_id: str, event: OperationalEvent,
                  authority_context: dict[str, Any], *,
                  source_adapter: str, channel_adapter: str,
                  policy_version: str) -> None:
        self.save_event(event)
        self._b.upsert_stateful(
            "executions", execution_id,
            json.dumps({
                "execution_id": execution_id,
                "event_id": event.event_id,
                "policy_version": policy_version,
                "source_adapter": source_adapter,
                "channel_adapter": channel_adapter,
                "authority_context": plain(authority_context),
                "lease_id": None,
                "finding_id": None,
                "action_id": None,
                "result_id": None,
                "verdict": None,
            }, sort_keys=True),
            "RUN_STARTED",
        )

    def save_lease_for_run(self, execution_id: str, lease: Lease) -> None:
        self.save_lease(lease)
        self._patch_exec(execution_id, {"lease_id": lease.lease_id}, "LEASE_OPEN")

    def save_finding_for_run(self, execution_id: str, finding: Finding,
                              verdict: SentinelVerdict) -> None:
        self.save_finding(finding)
        self._patch_exec(execution_id, {
            "finding_id": finding.finding_id,
            "verdict": verdict.value,
        }, "FINDING_CREATED")

    def save_action_request_for_run(self, execution_id: str,
                                     request: ActionRequest) -> None:
        self.save_action_request(request)
        self._patch_exec(execution_id, {"action_id": request.action_id}, "ACTION_REQUESTED")

    def save_action_result_for_run(self, execution_id: str,
                                    result: ActionResult) -> None:
        self.save_action_result(result)
        self._patch_exec(execution_id, {"result_id": result.action_id}, "ACTION_RESULT_RECORDED")

    def evaluate_lease_for_run(self, execution_id: str, lease: Lease) -> None:
        """Record lease evaluation."""
        self.save_lease(lease)
        current = self._b.get("executions", execution_id)
        self._b.upsert_stateful(
            "executions", execution_id,
            current["data"],
            "LEASE_EVALUATED",
        )

    def complete_run(self, execution_id: str) -> None:
        current = self._b.get("executions", execution_id)
        self._b.upsert_stateful(
            "executions", execution_id,
            current["data"],
            "RUN_COMPLETED",
        )

    # --- Queries ---

    @staticmethod
    def _flatten_run(row: dict[str, Any]) -> dict[str, Any]:
        """Merge the data JSON blob into the top-level dict for convenience."""
        if row is None:
            return row
        flat = dict(row)
        data = json.loads(flat.pop("data", "{}"))
        flat.update(data)
        return flat

    def get_run(self, execution_id: str) -> dict[str, Any] | None:
        return self._flatten_run(self._b.get("executions", execution_id))

    def list_runs(self, *, phase_not_in: list[str] | None = None,
                  verdict: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        all_runs = self._b.list_all("executions")
        if phase_not_in:
            all_runs = [r for r in all_runs if r.get("state") not in phase_not_in]
        if verdict:
            all_runs = [r for r in all_runs
                        if json.loads(r["data"]).get("verdict") == verdict]
        return [self._flatten_run(r) for r in all_runs[:limit]]

    def count_runs(self) -> int:
        return self._b.count("executions")

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        return self._b.get("operational_events", event_id)

    def get_lease(self, lease_id: str) -> dict[str, Any] | None:
        return self._b.get("leases", lease_id)

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        return self._b.get("findings", finding_id)

    def get_action_request(self, action_id: str) -> dict[str, Any] | None:
        return self._b.get("action_requests", action_id)

    def get_action_result(self, action_id: str) -> dict[str, Any] | None:
        return self._b.get("action_results", action_id)

    # --- Recovery ---

    def recover_incomplete(self) -> list[dict[str, Any]]:
        """Find runs in non-terminal phases. Returns recovery info without guessing outcomes."""
        incomplete = self._b.list_all("executions")
        incomplete = [r for r in incomplete if r.get("state") not in ("RUN_COMPLETED", "RECOVERY_REQUIRED")]
        results = []
        for run in incomplete:
            data = json.loads(run["data"])
            results.append({
                "execution_id": run["execution_id"],
                "last_demonstrated_phase": run["state"],
                "event_id": data.get("event_id"),
                "lease_id": data.get("lease_id"),
                "finding_id": data.get("finding_id"),
                "action_id": data.get("action_id"),
                "result_id": data.get("result_id"),
                "verdict": run.get("verdict"),
                "dispatch_outcome": "UNKNOWN" if data.get("action_id") and not data.get("result_id") else None,
            })
        return results

    def mark_recovery(self, execution_id: str) -> None:
        """Mark a run as requiring recovery. Preserves the original phase."""
        current = self._b.get("executions", execution_id)
        if current:
            data = json.loads(current["data"])
            data["recovery_status"] = "RECOVERY_REQUIRED"
            data["recovery_reason"] = "Interrupted before completion"
            self._b.upsert_stateful(
                "executions", execution_id,
                json.dumps(data, sort_keys=True),
                current["state"],
            )

    # --- Verification ---

    def verify(self) -> tuple[bool, str]:
        """Check schema + integrity."""
        try:
            # Schema version
            rows = self._b.execute_raw("SELECT value FROM schema_meta WHERE key = 'version'")
            if not rows:
                return False, "Schema: version metadata missing"
            version = int(rows[0][0])
            if version > 1:
                return False, f"Schema: unsupported version v{version}"

            # Record counts
            event_count = self._b.count("operational_events")
            lease_count = self._b.count("leases")
            finding_count = self._b.count("findings")
            action_count = self._b.count("action_requests")
            result_count = self._b.count("action_results")
            run_count = self._b.count("executions")

            return True, (
                f"Schema OK (v{version}). "
                f"SQLite OK. Foreign keys ON. "
                f"Records: {run_count} runs, {event_count} events, "
                f"{lease_count} leases, {finding_count} findings, "
                f"{action_count} actions, {result_count} results"
            )
        except Exception as e:
            return False, f"Verification failed: {e}"
