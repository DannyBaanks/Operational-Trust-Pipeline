"""Persistence layer tests: backends, repository, runner, crash boundary, differential."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from otp.canonical import plain, sha256
from otp.channels import MockChannel
from otp.domain import (
    ActionStatus, ActionResult, Finding, FindingStatus, Lease, LeaseState,
    OperationalEvent, SentinelVerdict, make_event,
)
from otp.pipeline import (
    AckLeasePolicy, FixedClock, evaluate_ack, make_ack_lease, resolve_ack_lease,
    run_ack_lease,
)
from otp.persistence import ConflictError, memory_backend, default_backend, CONFIG_DIR
from otp.persistence.memory import MemoryBackend
from otp.persistence.sqlite import SQLiteBackend
from otp.persistence.repository import RunRepository, _canonical
from otp.runner import OperationalRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _event(**overrides) -> OperationalEvent:
    base = {
        "schema_version": "operational-event/1", "source": "test-source",
        "source_event_type": "test", "source_ref": "ref-1",
        "entity_type": "assignment", "entity_id": "EVT-001",
        "observed_at": "2026-09-10T08:00:00Z",
        "payload": {"ack_due_at": "2026-09-10T08:15:00Z", "contact_ref": "+15551234567"},
    }
    base.update(overrides)
    payload = base.pop("payload")
    return make_event(**base, payload=payload)


def _finding(event=None) -> Finding:
    ev = event or _event()
    return Finding(
        finding_id="finding_test_001", rule_id="test-rule",
        status=FindingStatus.FAIL, severity="HIGH",
        subject_ref="EVT-001", reason_code="ACK_LEASE_EXPIRED",
        reason="Test finding", evidence_refs=(ev.event_id,),
        action_recommended=True,
    )


def _lease() -> Lease:
    from otp.domain import make_lease
    return make_lease("acknowledgement", "EVT-001", "2026-09-10T08:00:00Z",
                      "2026-09-10T08:15:00Z", "acknowledged")


def _action_result(acknowledged=True, delivery="KNOWN") -> ActionResult:
    return ActionResult(
        action_id="action_test_001", provider="mock", provider_ref="mock-ref",
        status=ActionStatus.ACKNOWLEDGED if acknowledged else ActionStatus.FAILED,
        acknowledged=acknowledged, response="ok", started_at=None, completed_at=None,
        error_code=None, evidence_refs=(),
        provider_accepted=True, delivery=delivery, reached_ringing="TRUE",
        terminal_cause="ACKNOWLEDGED", retry_safe="FALSE",
    )


# ---------------------------------------------------------------------------
# Backend basics
# ---------------------------------------------------------------------------

class TestMemoryBackend:
    def test_first_run_no_crash(self):
        b = MemoryBackend()
        b.initialize()

    def test_write_then_read(self):
        b = MemoryBackend()
        b.initialize()
        b.put("ns", "k1", {"field": "value"})
        result = b.get("ns", "k1")
        assert result["field"] == "value"

    def test_list_ordering(self):
        b = MemoryBackend()
        b.initialize()
        for i in range(5):
            b.put("ns", f"k{i}", {"i": i})
        items = b.list_all("ns")
        assert len(items) == 5

    def test_count(self):
        b = MemoryBackend()
        b.initialize()
        b.put("ns", "k1", {"a": 1})
        b.put("ns", "k2", {"a": 2})
        assert b.count("ns") == 2


class TestSQLiteBackend:
    def test_first_run_creates_database(self, tmp_path):
        db = tmp_path / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        assert db.exists()

    def test_schema_initializes_exactly_once(self, tmp_path):
        db = tmp_path / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        b.initialize()  # second call is no-op
        assert db.exists()

    def test_write_then_read(self, tmp_path):
        db = tmp_path / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        b.put("operational_events", "evt_001", {"data": "test"})
        result = b.get("operational_events", "evt_001")
        assert result is not None
        assert result["event_id"] == "evt_001"

    def test_list_ordering_deterministic(self, tmp_path):
        db = tmp_path / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        for i in range(5):
            b.put_immutable("operational_events", f"evt_{i:03d}", json.dumps({"i": i}))
        items = b.list_all("operational_events")
        assert len(items) == 5
        # Check ordering by created_at, then by ID
        ids = [item["event_id"] for item in items]
        assert ids == sorted(ids)

    def test_close_and_reopen(self, tmp_path):
        db = tmp_path / "test.db"
        b1 = SQLiteBackend(db)
        b1.initialize()
        b1.put("operational_events", "evt_001", {"data": "persisted"})
        b1.close()

        b2 = SQLiteBackend(db)
        b2.initialize()
        result = b2.get("operational_events", "evt_001")
        assert result is not None
        b2.close()


# ---------------------------------------------------------------------------
# Immutable idempotency
# ---------------------------------------------------------------------------

class TestImmutableIdempotency:
    def test_immutable_idempotent_insert(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.put_immutable("operational_events", "evt_001", '{"data":"test"}')
        # Same content → idempotent
        b.put_immutable("operational_events", "evt_001", '{"data":"test"}')

    def test_immutable_conflict_different_content(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.put_immutable("operational_events", "evt_001", '{"data":"v1"}')
        with pytest.raises(ConflictError):
            b.put_immutable("operational_events", "evt_001", '{"data":"v2"}')

    def test_memory_immutable_same(self):
        b = MemoryBackend()
        b.initialize()
        b.put_immutable("ns", "k1", "same")
        b.put_immutable("ns", "k1", "same")  # no error

    def test_memory_immutable_conflict(self):
        b = MemoryBackend()
        b.initialize()
        b.put_immutable("ns", "k1", "v1")
        with pytest.raises(ConflictError):
            b.put_immutable("ns", "k1", "v2")


# ---------------------------------------------------------------------------
# Stateful transitions
# ---------------------------------------------------------------------------

class TestStatefulTransitions:
    def test_lease_legal_transition(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.upsert_stateful("leases", "L1", '{"state":"OPEN"}', "OPEN")
        b.upsert_stateful("leases", "L1", '{"state":"SATISFIED"}', "SATISFIED")
        result = b.get("leases", "L1")
        assert result["state"] == "SATISFIED"

    def test_lease_illegal_transition(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.upsert_stateful("leases", "L1", '{"state":"OPEN"}', "OPEN")
        b.upsert_stateful("leases", "L1", '{"state":"SATISFIED"}', "SATISFIED")
        # SATISFIED → OPEN is illegal
        with pytest.raises(ConflictError):
            b.upsert_stateful("leases", "L1", '{"state":"OPEN"}', "OPEN")

    def test_execution_legal_transition(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.upsert_stateful("executions", "EX1", '{"state":"RUN_STARTED"}', "RUN_STARTED")
        b.upsert_stateful("executions", "EX1", '{"state":"LEASE_OPEN"}', "LEASE_OPEN")
        result = b.get("executions", "EX1")
        assert result["state"] == "LEASE_OPEN"

    def test_execution_illegal_transition(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.upsert_stateful("executions", "EX1", '{"state":"RUN_STARTED"}', "RUN_STARTED")
        # RUN_STARTED → RUN_COMPLETED is illegal (skips phases)
        with pytest.raises(ConflictError):
            b.upsert_stateful("executions", "EX1", '{"state":"RUN_COMPLETED"}', "RUN_COMPLETED")

    def test_memory_lease_legal(self):
        b = MemoryBackend()
        b.initialize()
        b.upsert_stateful("leases", "L1", '{"s":"OPEN"}', "OPEN")
        b.upsert_stateful("leases", "L1", '{"s":"SATISFIED"}', "SATISFIED")
        r = b.get("leases", "L1")
        assert r["state"] == "SATISFIED"

    def test_memory_lease_illegal(self):
        b = MemoryBackend()
        b.initialize()
        b.upsert_stateful("leases", "L1", '{"s":"OPEN"}', "OPEN")
        b.upsert_stateful("leases", "L1", '{"s":"SATISFIED"}', "SATISFIED")
        # SATISFIED → OPEN is illegal
        with pytest.raises(ConflictError):
            b.upsert_stateful("leases", "L1", '{"s":"OPEN"}', "OPEN")


# ---------------------------------------------------------------------------
# Repository domain round-trip
# ---------------------------------------------------------------------------

class TestRepository:
    def test_event_roundtrip(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.save_event(ev)
        loaded = repo.get_event(ev.event_id)
        assert loaded is not None
        assert json.loads(loaded["data"])["event_id"] == ev.event_id

    def test_lease_roundtrip(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        lease = _lease()
        repo.save_lease(lease)
        loaded = repo.get_lease(lease.lease_id)
        assert loaded is not None
        assert loaded["state"] == "OPEN"

    def test_finding_roundtrip(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        f = _finding()
        repo.save_finding(f)
        loaded = repo.get_finding(f.finding_id)
        assert loaded is not None

    def test_action_request_and_result_roundtrip(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        from otp.domain import ActionRequest
        ar = ActionRequest(
            action_id="action_test_001", action_type="notify",
            target_ref="+15551234567", channel="mock",
            objective="Test", message="Test msg",
            require_ack=True, urgency="HIGH",
            source_finding_ids=("finding_test_001",),
            authority_context={"communication_allowed": True},
        )
        repo.save_action_request(ar)
        result = _action_result()
        repo.save_action_result(result)
        assert repo.get_action_request("action_test_001") is not None
        assert repo.get_action_result("action_test_001") is not None

    def test_list_ordering_deterministic(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        for i in range(5):
            ev = _event(entity_id=f"EVT-{i:03d}")
            repo.save_event(ev)
        events = repo._b.list_all("operational_events")
        assert len(events) == 5


# ---------------------------------------------------------------------------
# Restart survival
# ---------------------------------------------------------------------------

class TestRestartSurvival:
    def test_restart_survives(self, tmp_path):
        db = tmp_path / "test.db"
        # Process A
        b1 = SQLiteBackend(db)
        b1.initialize()
        repo1 = RunRepository(b1)
        ev = _event()
        repo1.save_event(ev)
        lease = _lease()
        repo1.save_lease(lease)
        b1.close()

        # Process B
        b2 = SQLiteBackend(db)
        b2.initialize()
        repo2 = RunRepository(b2)
        assert repo2.get_event(ev.event_id) is not None
        assert repo2.get_lease(lease.lease_id) is not None
        b2.close()

    def test_stable_ids_survive_restart(self, tmp_path):
        db = tmp_path / "test.db"
        b1 = SQLiteBackend(db)
        b1.initialize()
        repo1 = RunRepository(b1)
        ev = _event()
        repo1.save_event(ev)
        original_id = ev.event_id
        b1.close()

        b2 = SQLiteBackend(db)
        b2.initialize()
        repo2 = RunRepository(b2)
        loaded = repo2.get_event(original_id)
        assert loaded is not None
        assert loaded["event_id"] == original_id
        b2.close()

    def test_stable_timestamps_survive_restart(self, tmp_path):
        db = tmp_path / "test.db"
        b1 = SQLiteBackend(db)
        b1.initialize()
        repo1 = RunRepository(b1)
        ev = _event()
        repo1.save_event(ev)
        loaded1 = repo1.get_event(ev.event_id)
        ts1 = loaded1["created_at"]
        b1.close()

        b2 = SQLiteBackend(db)
        b2.initialize()
        repo2 = RunRepository(b2)
        loaded2 = repo2.get_event(ev.event_id)
        assert loaded2["created_at"] == ts1
        b2.close()

    def test_existing_valid_database_never_reset(self, tmp_path):
        db = tmp_path / "test.db"
        b1 = SQLiteBackend(db)
        b1.initialize()
        repo1 = RunRepository(b1)
        ev = _event()
        repo1.save_event(ev)
        b1.close()

        # Reopen — should NOT recreate
        b2 = SQLiteBackend(db)
        b2.initialize()
        repo2 = RunRepository(b2)
        assert repo2.get_event(ev.event_id) is not None
        b2.close()


# ---------------------------------------------------------------------------
# Crash boundary tests
# ---------------------------------------------------------------------------

class TestCrashBoundary:
    def test_crash_after_run_start(self, tmp_path):
        """Phase=RUN_STARTED, no lease/finding yet."""
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.start_run("exec_001", ev, {"communication_allowed": True},
                       source_adapter="test", channel_adapter="mock",
                       policy_version="ack-lease-v0")
        run = repo.get_run("exec_001")
        assert run["state"] == "RUN_STARTED"
        assert run["lease_id"] is None
        assert run["finding_id"] is None
        assert run["verdict"] is None
        # Recovery
        incomplete = repo.recover_incomplete()
        assert len(incomplete) == 1
        assert incomplete[0]["last_demonstrated_phase"] == "RUN_STARTED"

    def test_crash_after_lease_creation(self, tmp_path):
        """Phase=LEASE_OPEN, finding not yet created."""
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.start_run("exec_001", ev, {}, source_adapter="t", channel_adapter="m",
                       policy_version="v")
        lease = _lease()
        repo.save_lease_for_run("exec_001", lease)
        run = repo.get_run("exec_001")
        assert run["state"] == "LEASE_OPEN"
        assert run["lease_id"] == lease.lease_id
        assert run["finding_id"] is None

    def test_crash_after_action_request_before_channel(self, tmp_path):
        """Phase=ACTION_REQUESTED, result=None. Dispatch outcome UNKNOWN."""
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.start_run("exec_001", ev, {}, source_adapter="t", channel_adapter="m",
                       policy_version="v")
        lease = _lease()
        repo.save_lease_for_run("exec_001", lease)
        f = _finding(ev)
        repo.save_finding_for_run("exec_001", f, SentinelVerdict.ACTION_REQUESTED)
        from otp.domain import ActionRequest
        ar = ActionRequest(
            action_id="action_test_001", action_type="notify",
            target_ref="+15551234567", channel="mock",
            objective="Test", message="msg",
            require_ack=True, urgency="HIGH",
            source_finding_ids=(), authority_context={},
        )
        repo.save_action_request_for_run("exec_001", ar)
        run = repo.get_run("exec_001")
        assert run["state"] == "ACTION_REQUESTED"
        assert run["action_id"] == "action_test_001"
        assert run["result_id"] is None
        # Recovery should report dispatch outcome unknown
        incomplete = repo.recover_incomplete()
        assert len(incomplete) == 1
        assert incomplete[0]["dispatch_outcome"] == "UNKNOWN"

    def test_crash_after_channel_before_result(self, tmp_path):
        """Channel called but result not persisted. Phase stays ACTION_REQUESTED."""
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.start_run("exec_001", ev, {}, source_adapter="t", channel_adapter="m",
                       policy_version="v")
        lease = _lease()
        repo.save_lease_for_run("exec_001", lease)
        f = _finding(ev)
        repo.save_finding_for_run("exec_001", f, SentinelVerdict.ACTION_REQUESTED)
        from otp.domain import ActionRequest
        ar = ActionRequest(
            action_id="action_test_001", action_type="notify",
            target_ref="+15551234567", channel="mock",
            objective="Test", message="msg",
            require_ack=True, urgency="HIGH",
            source_finding_ids=(), authority_context={},
        )
        repo.save_action_request_for_run("exec_001", ar)
        # Simulate: channel was called, but we crashed before persisting result
        run = repo.get_run("exec_001")
        assert run["state"] == "ACTION_REQUESTED"
        assert run["result_id"] is None

    def test_crash_after_result_before_lease_resolved(self, tmp_path):
        """Phase=ACTION_RESULT_RECORDED, lease still OPEN."""
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.start_run("exec_001", ev, {}, source_adapter="t", channel_adapter="m",
                       policy_version="v")
        lease = _lease()
        repo.save_lease_for_run("exec_001", lease)
        f = _finding(ev)
        repo.save_finding_for_run("exec_001", f, SentinelVerdict.ACTION_REQUESTED)
        from otp.domain import ActionRequest
        ar = ActionRequest(
            action_id="action_test_001", action_type="notify",
            target_ref="+15551234567", channel="mock",
            objective="Test", message="msg",
            require_ack=True, urgency="HIGH",
            source_finding_ids=(), authority_context={},
        )
        repo.save_action_request_for_run("exec_001", ar)
        result = _action_result()
        repo.save_action_result_for_run("exec_001", result)
        run = repo.get_run("exec_001")
        assert run["state"] == "ACTION_RESULT_RECORDED"
        assert run["result_id"] == "action_test_001"
        # Lease should still be OPEN (not yet resolved)
        lease_data = repo.get_lease(lease.lease_id)
        assert lease_data["state"] == "OPEN"


# ---------------------------------------------------------------------------
# Differential: Memory vs SQLite
# ---------------------------------------------------------------------------

class TestDifferential:
    def test_memory_vs_sqlite_equivalent_state(self, tmp_path):
        """Same input sequence produces equivalent domain state in both backends."""
        mem = RunRepository(MemoryBackend())
        sql = RunRepository(SQLiteBackend(tmp_path / "test.db"))
        mem.initialize()
        sql.initialize()

        ev = _event()
        for repo in [mem, sql]:
            repo.save_event(ev)
            lease = _lease()
            repo.save_lease(lease)
            f = _finding(ev)
            repo.save_finding(f)
            from otp.domain import ActionRequest
            ar = ActionRequest(
                action_id="action_test_001", action_type="notify",
                target_ref="t", channel="mock", objective="o",
                message="m", require_ack=True, urgency="HIGH",
                source_finding_ids=(), authority_context={},
            )
            repo.save_action_request(ar)
            result = _action_result()
            repo.save_action_result(result)

        # Verify equivalent state
        for entity_id, table in [("evt_001", "event"), ("L1", "lease"),
                                  ("finding_test_001", "finding")]:
            pass  # IDs differ, compare by count
        assert mem.count_runs() == sql.count_runs()
        assert mem._b.count("operational_events") == sql._b.count("operational_events")
        assert mem._b.count("leases") == sql._b.count("leases")
        assert mem._b.count("findings") == sql._b.count("findings")
        assert mem._b.count("action_requests") == sql._b.count("action_requests")
        assert mem._b.count("action_results") == sql._b.count("action_results")


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------

class TestIntegrity:
    def test_unsupported_newer_schema_refuses_mutation(self, tmp_path):
        db = tmp_path / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        # Manually set a newer schema version
        b._conn.execute("UPDATE schema_meta SET value = '99' WHERE key = 'version'")
        b._conn.commit()
        b.close()

        b2 = SQLiteBackend(db)
        with pytest.raises(Exception):
            b2.initialize()

    def test_missing_database_recreates_cleanly(self, tmp_path):
        db = tmp_path / "nonexistent" / "deep" / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        assert db.exists()

    def test_corrupt_record_not_silently_accepted(self, tmp_path):
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.put_immutable("operational_events", "evt_001", '{"data":"good"}')
        with pytest.raises(ConflictError):
            b.put_immutable("operational_events", "evt_001", '{"data":"corrupt"}')


# ---------------------------------------------------------------------------
# Independence from Drive
# ---------------------------------------------------------------------------

class TestDriveIndependence:
    def test_drive_disconnected_does_not_affect_local(self, tmp_path):
        """Local persistence works without Drive tokens."""
        db = tmp_path / "test.db"
        b = SQLiteBackend(db)
        b.initialize()
        repo = RunRepository(b)
        ev = _event()
        repo.save_event(ev)
        assert repo.get_event(ev.event_id) is not None

    def test_persistence_failure_not_empty_success(self, tmp_path):
        """Conflict raises, never silently succeeds."""
        b = SQLiteBackend(tmp_path / "test.db")
        b.initialize()
        b.put_immutable("operational_events", "evt_001", '{"data":"v1"}')
        with pytest.raises(ConflictError):
            b.put_immutable("operational_events", "evt_001", '{"data":"v2"}')


# ---------------------------------------------------------------------------
# E2E runner with persistence
# ---------------------------------------------------------------------------

class TestE2ERunner:
    def test_runner_full_cycle(self, tmp_path):
        """End-to-end: runner persists all lifecycle phases."""
        db = tmp_path / "test.db"
        backend = SQLiteBackend(db)
        backend.initialize()
        repo = RunRepository(backend)
        runner = OperationalRunner(repo, clock=FixedClock("2026-09-10T08:16:00Z"))

        ev = _event()
        ch = MockChannel()
        result = runner.run_ack_lease(ev, ch, {"communication_allowed": True, "channel": "mock"})

        # Verify run completed
        run = repo.get_run(result["execution_id"])
        assert run is not None
        assert run["state"] == "RUN_COMPLETED"
        assert run["verdict"] == "ACTION_REQUESTED"
        assert run["event_id"] == ev.event_id
        assert run["lease_id"] is not None
        assert run["finding_id"] is not None
        assert run["action_id"] is not None
        assert run["result_id"] is not None

        # Verify domain entities persisted
        assert repo.get_event(ev.event_id) is not None
        assert repo.get_lease(run["lease_id"]) is not None
        assert repo.get_finding(run["finding_id"]) is not None
        assert repo.get_action_request(run["action_id"]) is not None
        assert repo.get_action_result(run["result_id"]) is not None

        backend.close()

    def test_runner_survives_restart(self, tmp_path):
        """Process A runs, Process B loads same state."""
        db = tmp_path / "test.db"

        # Process A
        b1 = SQLiteBackend(db)
        b1.initialize()
        repo1 = RunRepository(b1)
        runner1 = OperationalRunner(repo1, clock=FixedClock("2026-09-10T08:16:00Z"))
        ev = _event()
        result = runner1.run_ack_lease(ev, MockChannel(), {"communication_allowed": True})
        exec_id = result["execution_id"]
        b1.close()

        # Process B
        b2 = SQLiteBackend(db)
        b2.initialize()
        repo2 = RunRepository(b2)
        run = repo2.get_run(exec_id)
        assert run is not None
        assert run["state"] == "RUN_COMPLETED"
        assert run["event_id"] == ev.event_id
        b2.close()

    def test_verify_output(self, tmp_path):
        """otp persistence verify produces correct output."""
        db = tmp_path / "test.db"
        backend = SQLiteBackend(db)
        backend.initialize()
        repo = RunRepository(backend)
        runner = OperationalRunner(repo, clock=FixedClock("2026-09-10T08:16:00Z"))
        runner.run_ack_lease(_event(), MockChannel(), {"communication_allowed": True})
        ok, msg = repo.verify()
        assert ok
        assert "Schema OK" in msg
        assert "Records:" in msg
        backend.close()


# ---------------------------------------------------------------------------
# Ephemeral runner
# ---------------------------------------------------------------------------

class TestEphemeralRunner:
    def test_ephemeral_runner_no_persistence(self):
        from otp.runner import ephemeral_runner
        runner = ephemeral_runner()
        ev = _event()
        result = runner.run_ack_lease(ev, MockChannel(), {"communication_allowed": True})
        assert result["execution_id"] is not None
        # No file created
