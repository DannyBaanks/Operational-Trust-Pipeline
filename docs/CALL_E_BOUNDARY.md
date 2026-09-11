# CALL-E Boundary

`CalleChannel` is a thin optional adapter. Its default is `live=False`, yielding `NOT_DEMONSTRATED` without importing SDK types or placing a call. A live path requires an explicitly supplied ISyCoCALL-e `PhoneCallCapability`, resolved phone target metadata, and CALL-E's own authority decision.

OTP deciding `ACTION_REQUESTED` means only that operational policy permits requesting communication. It does not mean the phone capability is authorized. CALL-E's capability evaluates technical availability, explicit grant, policy allowance, and execution verification. A CALL-E mock must never be described as live.

## Delivery-uncertainty classification

When live execution is enabled, `CalleChannel` classifies results on two axes that providers commonly conflate:

| Axis | Values | Meaning |
|---|---|---|
| `provider_accepted` | `True` / `False` | The telephony platform accepted the task and attempted routing |
| `delivery` | `KNOWN` / `UNKNOWN` / `NOT_DEMONSTRATED` | Whether the recipient's device actually received and answered |
| `reached_ringing` | `TRUE` / `FALSE` / `UNKNOWN` | Whether the handset produced a ringing signal |
| `terminal_cause` | e.g. `SUCCESS`, `ByCallee`, `LIVE_DISABLED` | The platform-reported terminal state |

### The NO ANSWER invariant

A `NO ANSWER` / `ByCallee` / 0s duration result means:

- `provider_accepted = True` — the platform ran
- `delivery = UNKNOWN` — there is no signal the handset rang
- `reached_ringing = UNKNOWN` — no ringing evidence
- `recipient_acknowledged()` returns **False**

**This is the boundary.** OTP will NOT transition an acknowledgement lease to `SATISFIED` from a `NO ANSWER` result, regardless of duration or provider labels. The pipeline treats it as `EXPIRED` (if past deadline) or `OPEN` (if before deadline).

Rationale: from the CALL-E/platform layer alone, we cannot distinguish:
1. Handset off / airplane mode
2. Carrier routing failure
3. Handset rang but user chose not to answer
4. Carrier accepted but never forwarded to handset

Without a `reached_ringing` signal, the safe classification is `UNKNOWN`, not "recipient did not answer".

### Receipt evidence

Every `CalleChannel` result includes the five uncertainty fields in the evidence receipt. This makes the classification auditable: a future consumer can query `delivery != "KNOWN"` to find all uncertain outcomes without re-running the call.

## Scope boundary

No live credential inspection or phone-call execution is performed by this project unless explicitly opted in via `OTP_LIVE_TEST=1` and human authorization.
