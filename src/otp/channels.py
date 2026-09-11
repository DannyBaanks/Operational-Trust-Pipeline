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
                            True, "received", None, None, None,
                            provider_accepted=True, delivery="KNOWN", reached_ringing="TRUE",
                            terminal_cause="ACKNOWLEDGED", retry_safe="FALSE")


class DummyChannel(MockChannel):
    identity = "dummy-channel/1"


class CalleChannel:
    """Thin optional bridge. It defaults to non-execution and preserves CALL-E authority.

    Live execution requires opt-in and a supplied ISyCoCALL-e PhoneCallCapability.
    A CALL-E NO ANSWER with duration=0 and no transcript/received signal maps to
    DELIVERY_UNCERTAIN, not to recipient_acknowledged.
    """
    identity = "calle-channel/1"
    def __init__(self, *, live: bool = False, capability=None, caller: str = "otp") -> None:
        self.live, self.capability, self.caller = live, capability, caller

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("isyco_calle") is not None

    def send(self, request: ActionRequest) -> ActionResult:
        if not self.live or self.capability is None:
            return ActionResult(request.action_id, self.identity, None, ActionStatus.NOT_DEMONSTRATED, False,
                                None, None, None, "LIVE_DISABLED", (),
                                provider_accepted=False, delivery="NOT_DEMONSTRATED",
                                reached_ringing="UNKNOWN", terminal_cause="LIVE_DISABLED",
                                retry_safe="UNKNOWN")
        from isyco_calle.domain.contract import PhoneCallRequest
        from isyco_calle.domain.result import PhoneCallStatus
        phone = request.metadata.get("phone")
        if not phone:
            return ActionResult(request.action_id, self.identity, None, ActionStatus.REJECTED, False,
                                None, None, None, "TARGET_UNRESOLVED", (),
                                provider_accepted=False, delivery="NOT_DEMONSTRATED",
                                reached_ringing="UNKNOWN", terminal_cause="TARGET_UNRESOLVED",
                                retry_safe="UNKNOWN")
        result = self.capability.call(PhoneCallRequest(action="phone.call", objective=request.objective, phone=phone,
                                                       idempotency_key=request.action_id), caller=self.caller)

        if result.status is PhoneCallStatus.SUCCESS:
            return ActionResult(
                request.action_id, result.provider or self.identity, result.request_id,
                ActionStatus.ACKNOWLEDGED, True,
                result.summary, result.started_at, result.finished_at,
                "SUCCESS", tuple(result.raw_evidence_reference or ()),
                provider_accepted=True, delivery="KNOWN", reached_ringing="TRUE",
                terminal_cause="SUCCESS", retry_safe="FALSE",
            )

        # Non-success: classify the CALL-E/Carrier boundary honestly.
        # A "NO ANSWER" / ByCallee / duration=0 end state is NOT proof that the
        # destination handset actually received ringing. Without a ringing/notify
        # signal, the strongest safe conclusion is UNKNOWN, not "recipient did
        # not answer". This is the core invariant that distinguishes OTP from a
        # naive provider-label passthrough.
        return ActionResult(
            request.action_id, result.provider or self.identity, result.request_id,
            ActionStatus.FAILED, False,
            result.summary, result.started_at, result.finished_at,
            result.status.value, tuple(result.raw_evidence_reference or ()),
            provider_accepted=True, delivery="UNKNOWN", reached_ringing="UNKNOWN",
            terminal_cause=result.status.value, retry_safe="UNKNOWN",
        )
