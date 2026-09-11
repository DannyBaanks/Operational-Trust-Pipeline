# Trust Boundary

Three layers. Each one is a separate claim with separate evidence.

## Layer 1: Provider accepted the task

The telephony platform accepted the API call and began processing. This means nothing about whether the destination handset received anything.

- `provider_accepted=True` → the platform ran
- `provider_accepted=False` → the platform did not run (blocked, transport error, offline)

**This is NOT delivery.** A provider can accept a task and never reach the handset.

## Layer 2: Phone reached the handset

The destination device received the call and produced a signal (ringing, voicemail prompt, etc.).

- `reached_ringing=TRUE` → the handset rang
- `reached_ringing=FALSE` → the handset was reached but did not ring (e.g. busy signal)
- `reached_ringing=UNKNOWN` → no evidence either way

**This is NOT answer.** The handset can ring without anyone answering.

## Layer 3: Recipient answered

The human (or system) on the other end acknowledged the communication.

- `delivery=KNOWN` + `acknowledged=True` → the recipient answered
- `delivery=UNKNOWN` → we do not know
- `delivery=NOT_DEMONSTRATED` → we did not try, or the provider never responded

## What OTP does with each case

| Provider state | `provider_accepted` | `delivery` | `reached_ringing` | Lease effect |
|---|---|---|---|---|
| Mock success | `True` | `KNOWN` | `TRUE` | `SATISFIED` |
| CALL-E answered | `True` | `KNOWN` | `TRUE` | `SATISFIED` |
| CALL-E NO ANSWER, 0s | `True` | `UNKNOWN` | `UNKNOWN` | `EXPIRED` (or `OPEN` if before deadline) |
| Provider concurrency blocked | `False` | `NOT_DEMONSTRATED` | `UNKNOWN` | `EXPIRED` (or `OPEN`) |
| Provider accepted, no evidence | `True` | `UNKNOWN` | `UNKNOWN` | `EXPIRED` (or `OPEN`) |
| Transport failure | `False` | `NOT_DEMONSTRATED` | `UNKNOWN` | `EXPIRED` (or `OPEN`) |
| OTP offline (live=False) | `False` | `NOT_DEMONSTRATED` | `UNKNOWN` | No dispatch |

## The invariants

1. **`provider_accepted=True` alone does not satisfy a lease.** Only `recipient_acknowledged()` (requires `acknowledged=True` AND `delivery != "NOT_DEMONSTRATED"`) transitions a lease to `SATISFIED`.

2. **`NO ANSWER` without delivery evidence = `UNKNOWN`, not "recipient did not answer."** Without a `reached_ringing` signal, we cannot distinguish handset-off from carrier-failure from user-chose-not-to-answer. The safe classification is UNKNOWN.

3. **The Sentinel cannot upgrade delivery.** Only the channel adapter, with direct provider access, sets `delivery=KNOWN`. The Sentinel sees the result post-hoc.

4. **A receipt with `delivery=UNKNOWN` is a valid negative result.** It is not a pipeline failure. It is the pipeline correctly refusing to overstate what it knows.

5. **Concurrency blocked is NOT delivery failure.** `PROVIDER_UNAVAILABLE` means the shared line was busy. It says nothing about the destination. Retry is safe.
