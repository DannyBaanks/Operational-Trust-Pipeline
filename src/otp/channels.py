"""Channel adapters. No adapter is imported by the domain layer."""
from __future__ import annotations

import importlib.util

from .canonical import stable_id
from .domain import ActionRequest, ActionResult, ActionStatus


class MockChannel:
    identity = "mock-channel/1"
    def __init__(self) -> None:
        self.requests: list[ActionRequest] = []
    def send(self, request: ActionRequest) -> ActionResult:
        self.requests.append(request)
        return ActionResult(request.action_id, self.identity, stable_id("mock", request.action_id), ActionStatus.ACKNOWLEDGED,
                            True, "received", None, None, None)


class DummyChannel(MockChannel):
    identity = "dummy-channel/1"


class CalleChannel:
    """Thin optional bridge. It defaults to non-execution and preserves CALL-E authority."""
    identity = "calle-channel/1"
    def __init__(self, *, live: bool = False, capability=None, caller: str = "otp") -> None:
        self.live, self.capability, self.caller = live, capability, caller

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("isyco_calle") is not None

    def send(self, request: ActionRequest) -> ActionResult:
        if not self.live or self.capability is None:
            return ActionResult(request.action_id, self.identity, None, ActionStatus.NOT_DEMONSTRATED, False,
                                None, None, None, "LIVE_DISABLED", ())
        from isyco_calle.domain.contract import PhoneCallRequest
        from isyco_calle.domain.result import PhoneCallStatus
        phone = request.metadata.get("phone")
        if not phone:
            return ActionResult(request.action_id, self.identity, None, ActionStatus.REJECTED, False, None, None, None, "TARGET_UNRESOLVED")
        result = self.capability.call(PhoneCallRequest(action="phone.call", objective=request.objective, phone=phone,
                                                       idempotency_key=request.action_id), caller=self.caller)
        status = ActionStatus.ACKNOWLEDGED if result.status is PhoneCallStatus.SUCCESS else ActionStatus.REJECTED
        return ActionResult(request.action_id, result.provider or self.identity, result.request_id, status, False,
                            result.summary, result.started_at, result.finished_at, result.status.value, tuple(result.raw_evidence_reference or ()))
