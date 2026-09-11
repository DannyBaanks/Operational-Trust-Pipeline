# LAN Channel

Local-network transport for the OTP demo. Proves that the pipeline's decision and evidence layers work with **any** transport — not just telephony.

## Architecture

```
RoadStar data
    ↓
OTP (core)
    ↓
Finding / Lease
    ↓
Sentinel → ACTION_REQUESTED
    ↓
ActionRequest (structured, bounded)
    ↓
LanChannel adapter
    ↓
HTTP POST → local Flask relay (:8787)
    ↓
Web page on phone / laptop (same Wi-Fi)
    ↓
[ACKNOWLEDGE] or [CAN'T RESPOND]
    ↓
Response polled by adapter
    ↓
ActionResult → EvidenceReceipt
```

## How to run the demo

```bash
# Start the relay + run the pipeline (blocks until human responds or timeout)
py -m otp.cli demo ack-lease --channel lan

# The relay prints a URL like:
# Relay running at http://127.0.0.1:8787/receiver?token=<uuid>

# Open that URL on any phone/laptop on the same Wi-Fi.
# Tap ACKNOWLEDGE. The pipeline completes on the laptop.
```

For the hackathon demo without a phone:

```bash
# Deterministic mock path (no network needed)
py -m otp.cli demo ack-lease
```

## Security bounds

| Property | Status |
|---|---|
| Shell access | None |
| Arbitrary code execution | None |
| Filesystem authority | None (in-memory stores) |
| Session token | UUID4, per relay start |
| Device discovery | None |
| Voice / push / PTT | None |

## What it proves

OTP's core decision (when to act, to whom, why, under what authority) is independent of the last mile. The same `ActionRequest` interface can drive:

- LAN relay (this demo)
- CALL-E telephony (optional, when available)
- SMS gateway
- Email
- Radio dispatcher
- PTT system
- Satellite uplink

**The product ends where it should:** decide, route, record. The last mile is someone else's infrastructure.

## Files

| File | Purpose |
|---|---|
| `src/otp/channels.py` (LanChannel) | Adapter: sends request, polls response |
| `src/otp/lan_relay.py` | Flask relay: serves web page, stores requests/responses |
| `src/otp/templates/lan_receiver.html` | Minimal mobile-friendly alert page |
| `tests/test_lan_channel.py` | 11 tests: auth, cycle, adapter, pipeline, receipts |
