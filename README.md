# Operational Trust Pipeline

Provider-agnostic bounded operational action requests with verifiable evidence.

OTP turns operational state into bounded, verifiable human-action requests without coupling the decision layer to a data source or communication provider.

```
RoadStar data → normalize → evaluate → lease/policy → Sentinel → action request → channel → acknowledgement → receipt
```

## Quick Start

```bash
# Run tests (64 passing)
py -m pytest -q

# Deterministic demo (mock channel, no network)
py -m otp.cli demo ack-lease

# GUI control room (requires PySide6)
otp gui

# CLI with LAN channel (opens relay on :8787)
py -m otp.cli demo ack-lease --channel lan

# Google Drive sync (persistence)
pip install -e ".[drive]"
otp drive auth
otp drive sync
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Source Adapter        Core OTP             Channel Adapter          │
│  ┌──────────┐    ┌─────────────────┐    ┌──────────────────┐       │
│  │ RoadStar │───→│ Normalize       │───→│ MockChannel      │       │
│  │ workbook │    │ Evaluate        │    │ LanChannel       │       │
│  └──────────┘    │ Sentinel        │    │ CalleChannel     │       │
│                  │ Lease/Policy    │    │ (optional)       │       │
│                  │ Evidence        │    └──────────────────┘       │
│                  └────────┬────────┘                                │
│                           │                                         │
│                  ┌────────▼────────┐                                │
│                  │  Google Drive   │  ← SHA-256 evidence backup     │
│                  │  Sync (OAuth2)  │  ← Ledger + receipts           │
│                  └─────────────────┘                                │
└──────────────────────────────────────────────────────────────────────┘
```

**Core = decision + evidence.** Source adapters normalize raw data into `OperationalEvent`. Channel adapters deliver `ActionRequest` and return `ActionResult`. The core never imports either layer.

## What OTP Proves

1. **Decide**: When does a trip need human attention? (AckLeasePolicy, DeliveryTimingPolicy, HosCapacityPolicy)
2. **Route**: To whom, by what channel, under what authority? (Sentinel deny-by-default)
3. **Record**: What happened, with SHA-256 chained evidence receipts?
4. **Persist**: Receipts and ledger sync to Google Drive — no data loss on restart.

The last mile is someone else's infrastructure. OTP ends where it should.

## Delivery Uncertainty

A provider accepting a task ≠ the recipient answering. OTP separates these claims:

| Field | Values | Meaning |
|---|---|---|
| `provider_accepted` | True/False | Platform ran |
| `delivery` | KNOWN/UNKNOWN/NOT_DEMONSTRATED | Recipient answered? |
| `reached_ringing` | TRUE/FALSE/UNKNOWN | Handset rang? |
| `recipient_acknowledged()` | True/False | **Only this satisfies a lease** |

`NO ANSWER` + 0s duration = `delivery=UNKNOWN`, not "recipient did not answer."

## Google Drive Sync

Evidence and ledger persist across restarts by syncing to your Google Drive. Only your own files — OTP never reads, deletes, or shares anything.

```bash
# One-time setup
pip install -e ".[drive]"

# 1. Create Google Cloud project → enable Drive API → OAuth2 credentials
# 2. Download credentials.json to ~/.otp/credentials.json
# 3. Authenticate
otp drive auth          # opens browser, paste token

# 4. Sync
otp drive sync          # uploads ledger.jsonl + evidence/*.json
otp drive status        # show sync count + last sync time
otp drive disconnect    # remove token
```

**What syncs:** `ledger.jsonl` (SHA-256 chained) + all receipt JSON files. Nothing else.

**Conflict detection:** If two machines sync the same file, Drive detects the hash mismatch and keeps both versions. The ledger chain detects reordering/insertion/deletion on verify.

**GUI indicator:** Status bar shows `Drive: connected` (green) or `Drive: not connected` (gray). Menu: `Drive > Connect / Sync / Status / Disconnect`.

## Trip States

| State | Color | Meaning |
|---|---|---|
| CRITICAL | Red | Overdue + no ack |
| AT RISK | Orange | Will miss deadline |
| WAITING ACK | Orange | Request sent, no response |
| DELIVERY UNCERTAIN | Gray | Provider accepted, no proof |
| ON TIME | Dim | Within window |
| RESOLVED | Green | Acknowledged, verified |

## Channels

| Channel | Status | Use case |
|---|---|---|
| MockChannel | **Active** | Deterministic demo, tests |
| LanChannel | **Active** | Local network demo (Flask relay + web page) |
| CalleChannel | Optional | CALL-E telephony (live=False by default) |
| Google Drive | **Active** | Evidence persistence (OAuth2, user's own Drive) |

## Hackathon Demo (90 seconds)

1. `otp gui` — window opens maximized, trips sorted by delta
2. Trip 28471 is red: ETA 14:32 > DELIVER_BY 14:05 (+27 min)
3. Click "Request ACK" — modal shows local URL
4. Open URL on phone — tap ACKNOWLEDGE
5. Modal auto-updates: "ACKNOWLEDGED" + receipt hash ✓ VERIFIED
6. Main window: CRITICAL drops, RESOLVED rises
7. `otp drive sync` — evidence backed up to Google Drive

**Narrative**: "The system identified which trips needed attention, routed the request to a local device, received acknowledgement, produced a verifiable receipt, and backed it up to the operator's own Google Drive."

## Project Structure

```
src/otp/
├── canonical.py        # SHA-256, canonical JSON, stable IDs
├── domain.py           # OperationalEvent, Lease, Finding, ActionRequest/Result
├── contracts.py        # Protocol interfaces (Clock, SourceAdapter, ChannelProvider)
├── pipeline.py         # AckLeasePolicy, DeliveryTimingPolicy, HosCapacityPolicy, Sentinel
├── evidence.py         # Receipt + ledger (SHA-256 chained)
├── roadstar.py         # RoadStar workbook adapter (Dispatch + Driver)
├── channels.py         # MockChannel, DummyChannel, LanChannel, CalleChannel
├── drive_sync.py       # Google Drive sync (OAuth2 + upload + conflict detection)
├── lan_relay.py        # Flask relay for LAN demo
├── cli.py              # CLI: doctor, demo, gui, verify, ledger, drive
├── gui/                # PySide6 control room
│   ├── main_window.py  # QMainWindow + menus + splitter + Drive sync
│   ├── trip_table.py   # Sortable QTableView
│   ├── detail_panel.py # WHY / ACTION / STATUS / EVIDENCE
│   ├── lan_modal.py    # Request acknowledgement dialog
│   ├── trip_model.py   # TripItem + state computation
│   ├── workers.py      # Background threads
│   ├── styles.py       # Dark theme
│   └── icons.py        # State indicator icons
└── templates/
    └── lan_receiver.html  # Mobile alert page
```

## Tests

```bash
py -m pytest -q          # 64 passed, 1 skipped
py -m pytest -v          # verbose
py -m pytest -k gui      # GUI unit tests only
py -m pytest -k drive    # Drive sync tests (mocked)
```

| Category | Count |
|---|---|
| Core vertical slice | 13 |
| Delivery uncertainty | 6 |
| Provider boundary | 5 |
| LAN channel | 11 |
| Drive sync (mocked) | 10 |
| GUI unit (trip_model, icons) | 19 |
| GUI widget smoke | 5 |
| Live CALL-E (skipped) | 1 |

## Evidence

Receipts bind event, lease, finding, action, and result with SHA-256. Ledger entries chain to the previous receipt hash. Offline verification detects altered components, reordered entries, inserted entries, and deleted middle entries.

```bash
py -m otp.cli demo ack-lease --evidence-dir ./evidence
py -m otp.cli verify ./evidence/<execution_id>.json
py -m otp.cli ledger verify ./evidence/ledger.jsonl
```

## License

Internal hackathon project. Not for production use.
