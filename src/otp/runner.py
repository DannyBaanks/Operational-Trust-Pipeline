"""OperationalRunner — lifecycle orchestration with durability.

The domain pipeline functions are pure.
The Runner owns persistence lifecycle and channel execution.
This is the canonical durable orchestration path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .domain import (
    ActionRequest, ActionResult, Finding, Lease, OperationalEvent,
    SentinelVerdict, make_lease,
)
from .pipeline import (
    AckLeasePolicy, Clock, ChannelProvider, SystemClock,
    evaluate_ack, execution_id, make_ack_lease, resolve_ack_lease,
)
from .persistence.repository import RunRepository


class OperationalRunner:
    """Durable pipeline execution.

    Persists lifecycle transitions at each phase.
    Persists ActionRequest BEFORE channel.send().
    Never infers success or failure from partial state.
    """

    def __init__(self, repository: RunRepository, clock: Clock | None = None) -> None:
        self._repo = repository
        self._clock = clock or SystemClock()

    def run_ack_lease(self, event: OperationalEvent, channel: ChannelProvider,
                      authority_context: dict[str, Any]) -> dict[str, Any]:
        """Run the ack-lease pipeline with full lifecycle persistence."""
        # Compute execution_id deterministically
        lease = make_ack_lease(event, self._clock)
        policy = AckLeasePolicy()
        exec_id = execution_id(event, lease, policy)

        # Phase 1: RUN_STARTED
        self._repo.start_run(
            exec_id, event, authority_context,
            source_adapter=event.source,
            channel_adapter=channel.identity,
            policy_version=policy.version,
        )

        # Phase 2: LEASE_OPEN
        self._repo.save_lease_for_run(exec_id, lease)

        # Phase 3: FINDING_CREATED
        finding, verdict, action = evaluate_ack(event, lease, self._clock, authority_context)
        self._repo.save_finding_for_run(exec_id, finding, verdict)

        # Phase 4: ACTION_REQUESTED (BEFORE channel call)
        if action:
            self._repo.save_action_request_for_run(exec_id, action)

        # Phase 5: CHANNEL CALL (external side effect)
        result = channel.send(action) if action else None

        # Phase 6: ACTION_RESULT_RECORDED
        if result:
            self._repo.save_action_result_for_run(exec_id, result)

        # Phase 7: LEASE_EVALUATED
        lease = resolve_ack_lease(lease, finding, result, self._clock)
        self._repo.evaluate_lease_for_run(exec_id, lease)

        # Phase 8: RUN_COMPLETED
        self._repo.complete_run(exec_id)

        return {
            "execution_id": exec_id,
            "event": event,
            "lease": lease,
            "finding": finding,
            "verdict": verdict,
            "action": action,
            "result": result,
            "policy_version": policy.version,
            "source_adapter": event.source,
            "channel_adapter": channel.identity,
        }


def default_runner() -> OperationalRunner:
    """Canonical entrypoint. SQLite persistence at ~/.otp/otp.db."""
    from .persistence import default_backend
    return OperationalRunner(repository=RunRepository(default_backend()))


def ephemeral_runner() -> OperationalRunner:
    """In-memory backend for tests and explicit ephemeral runs."""
    from .persistence import memory_backend
    return OperationalRunner(repository=RunRepository(memory_backend()))
