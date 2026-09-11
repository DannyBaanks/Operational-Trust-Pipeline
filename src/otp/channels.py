"""Channel adapters. No adapter is imported by the domain layer."""
from __future__ import annotations

import importlib.util
import json
import time
import urllib.request
import urllib.error

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


class LanChannel:
    """Local-network transport for the OTP demo.

    Sends a structured ActionRequest to a local relay server, which displays
    it on a web page. The human taps ACK or REJECT. The response is polled
    and returned as an ActionResult.

    Security: session token required, no shell, no arbitrary code, no
    filesystem authority. The web page is a minimal single-purpose receiver.
    """
    identity = "lan-channel/1"

    def __init__(self, relay_url: str, token: str, *, timeout: float = 300.0, poll_interval: float = 2.0) -> None:
        self.relay_url = relay_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.poll_interval = poll_interval

    def send(self, request: ActionRequest) -> ActionResult:
        sent_at = time.time()
        payload = {
            "request_id": request.action_id,
            "reason": request.objective,
            "subject_ref": request.target_ref,
            "severity": request.urgency,
            "source_adapter": request.channel,
        }

        # Inject into relay store
        inject_body = json.dumps({"request_id": request.action_id, "payload": payload}).encode()
        req = urllib.request.Request(
            f"{self.relay_url}/api/inject",
            data=inject_body,
            headers={"Content-Type": "application/json", "X-Session-Token": self.token},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    return ActionResult(request.action_id, self.identity, None,
                                        ActionStatus.PROVIDER_UNAVAILABLE, False,
                                        None, None, None, "RELAY_INJECT_FAILED", (),
                                        provider_accepted=False, delivery="NOT_DEMONSTRATED",
                                        reached_ringing="UNKNOWN", terminal_cause="RELAY_ERROR",
                                        retry_safe="UNKNOWN")
        except (urllib.error.URLError, OSError):
            return ActionResult(request.action_id, self.identity, None,
                                ActionStatus.PROVIDER_UNAVAILABLE, False,
                                None, None, None, "RELAY_UNREACHABLE", (),
                                provider_accepted=False, delivery="NOT_DEMONSTRATED",
                                reached_ringing="UNKNOWN", terminal_cause="TRANSPORT_ERROR",
                                retry_safe="UNKNOWN")

        # Poll for human response
        deadline = sent_at + self.timeout
        while time.time() < deadline:
            try:
                poll_req = urllib.request.Request(
                    f"{self.relay_url}/api/status/{request.action_id}",
                    headers={"X-Session-Token": self.token},
                )
                with urllib.request.urlopen(poll_req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    if data.get("responded"):
                        r = data["response"]
                        return ActionResult(
                            request.action_id, self.identity, None,
                            ActionStatus.ACKNOWLEDGED if r["acknowledged"] else ActionStatus.REJECTED,
                            r["acknowledged"], r.get("message"), None,
                            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["received_at"])),
                            None, (),
                            provider_accepted=True,
                            delivery="KNOWN" if r["acknowledged"] else "UNKNOWN",
                            reached_ringing="TRUE",
                            terminal_cause="ACKNOWLEDGED" if r["acknowledged"] else "REJECTED",
                            retry_safe="FALSE" if r["acknowledged"] else "UNKNOWN",
                        )
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(self.poll_interval)

        return ActionResult(request.action_id, self.identity, None,
                            ActionStatus.FAILED, False,
                            None, None, None, "HUMAN_TIMEOUT", (),
                            provider_accepted=True, delivery="UNKNOWN",
                            reached_ringing="UNKNOWN", terminal_cause="TIMEOUT",
                            retry_safe="UNKNOWN")
