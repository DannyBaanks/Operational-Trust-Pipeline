# Operational Trust Pipeline

Provider-agnostic bounded operational action requests with verifiable evidence.

OTP turns operational state into bounded, verifiable human-action requests without coupling the decision layer to a data source or communication provider.

```
RoadStar data → normalize → evaluate → lease/policy → Sentinel → action request → channel → acknowledgement → receipt
```

## Quick Start

```bash
# Run tests (107 passing)
py -m pytest -q

# Deterministic demo (mock channel, no network, persists to ~/.otp/otp.db)
py -m otp.cli demo ack-lease

# Ephemeral demo (in-memory, no disk writes)
py -m otp.cli demo ack-lease --ephemeral

# GUI control room (requires PySide6)
otp gui

# CLI with LAN channel (opens relay on :8787)
py -m otp.cli demo ack-lease --channel lan

# Google Drive sync
pip install -e ".[drive]"
otp drive auth
otp drive sync

# Persistence status
otp persistence status
otp persistence verify
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Source Adapter        Core OTP              Channel Adapter             │
│  ┌──────────┐    ┌──────────────────┐    ┌───────────────────┐          │
│  │ RoadStar │───→│ Normalize        │───→│ MockChannel       │          │
│  │ workbook │    │ Evaluate         │    │ LanChannel        │          │
│  └──────────┘    │ Sentinel         │    │ CalleChannel      │          │
│                  │ Lease/Policy     │    │ (optional)        │          │
│                  │ Evidence         │    └───────────────────┘          │
│                  └────────┬─────────┘                                   │
│                           │                                             │
│              ┌────────────▼────────────┐                                │
│              │     OperationalRunner   │  lifecycle orchestration        │
│              │   ┌─────────────────┐   │                                │
│              │   │  Persistence    │   │  SQLite (default) or Memory    │
│              │   │  ~/.otp/otp.db  │   │  crash-recoverable             │
│              │   └─────────────────┘   │                                │
│              └─────────────────────────┘                                │
│                           │                                             │
│              ┌────────────▼────────────┐                                │
│              │   Google Drive Sync     │  SHA-256 evidence backup       │
│              └─────────────────────────┘                                │
└──────────────────────────────────────────────────────────────────────────┘
```

**Core = decision + evidence.** Source adapters normalize raw data into `OperationalEvent`. Channel adapters deliver `ActionRequest` and return `ActionResult`. The core never imports either layer.

## What OTP Proves

1. **Decide**: When does a trip need human attention? (AckLeasePolicy, DeliveryTimingPolicy, HosCapacityPolicy)
2. **Route**: To whom, by what channel, under what authority? (Sentinel deny-by-default)
3. **Record**: What happened, with SHA-256 chained evidence receipts?
4. **Persist**: Lifecycle state survives process restarts (SQLite WAL mode, crash-recoverable).

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

## Persistence

Every pipeline run persists lifecycle state before external side effects. On restart, `recover_incomplete()` surfaces interrupted runs without guessing outcomes.

### Lifecycle Phases

```
RUN_STARTED → LEASE_OPEN → FINDING_CREATED → ACTION_REQUESTED → ACTION_RESULT_RECORDED → LEASE_EVALUATED → RUN_COMPLETED
```

Each phase is persisted **before** the corresponding external action (e.g., `ACTION_REQUESTED` is written before `channel.send()`). If the process crashes after `ACTION_REQUESTED` but before receiving a result, recovery marks the dispatch outcome as `UNKNOWN`.

### Backend

| Backend | Storage | Use case |
|---|---|---|
| SQLiteBackend (default) | `~/.otp/otp.db` | Persistent runs, survives restart |
| MemoryBackend | dict (no disk) | Tests, `--ephemeral` flag |

SQLite uses WAL mode, FK constraints, and explicit idempotency rules:
- **Immutable** (events, findings, actions, results): same ID + same content = idempotent; different content = `ConflictError`
- **Stateful** (leases, executions): same state + same data = idempotent; illegal transitions = `ConflictError`

### CLI

```bash
otp persistence status          # backend type, db path, record counts
otp persistence verify          # schema integrity check
otp persistence path            # show db file location
otp persistence recover         # list incomplete runs (crash recovery)
```

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
├── canonical.py            # SHA-256, canonical JSON, stable IDs
├── domain.py               # OperationalEvent, Lease, Finding, ActionRequest/Result
├── contracts.py            # Protocol interfaces (Clock, SourceAdapter, ChannelProvider)
├── pipeline.py             # AckLeasePolicy, DeliveryTimingPolicy, HosCapacityPolicy, Sentinel
│                           # + pure helpers: make_ack_lease, evaluate_ack, resolve_ack_lease
├── evidence.py             # Receipt + ledger (SHA-256 chained)
├── roadstar.py             # RoadStar workbook adapter (Dispatch + Driver)
├── channels.py             # MockChannel, DummyChannel, LanChannel, CalleChannel
├── drive_sync.py           # Google Drive sync (OAuth2 + upload + conflict detection)
├── runner.py               # OperationalRunner — lifecycle orchestration + persistence
├── lan_relay.py            # Flask relay for LAN demo
├── cli.py                  # CLI: demo, doctor, gui, verify, ledger, drive, persistence
├── persistence/
│   ├── __init__.py         # default_backend(), memory_backend()
│   ├── protocol.py         # PersistenceBackend Protocol, PersistenceStatus
│   ├── errors.py           # PersistenceError, ConflictError, CorruptionError
│   ├── memory.py           # MemoryBackend — dict-backed, thread-safe
│   ├── sqlite.py           # SQLiteBackend — WAL mode, FK, auto-init schema
│   └── repository.py       # RunRepository — domain methods, idempotency, recovery
├── gui/                    # PySide6 control room
│   ├── main_window.py      # QMainWindow + menus + splitter + Drive sync
│   ├── trip_table.py       # Sortable QTableView
│   ├── detail_panel.py     # WHY / ACTION / STATUS / EVIDENCE
│   ├── lan_modal.py        # Request acknowledgement dialog
│   ├── trip_model.py       # TripItem + state computation
│   ├── workers.py          # Background threads
│   ├── styles.py           # Dark theme
│   └── icons.py            # State indicator icons
└── templates/
    └── lan_receiver.html   # Mobile alert page
```

## Tests

```bash
py -m pytest -q          # 107 passed, 1 skipped
py -m pytest -v          # verbose
py -m pytest -k gui      # GUI unit tests only
py -m pytest -k drive    # Drive sync tests (mocked)
py -m pytest -k persist  # Persistence layer tests
```

| Category | Count |
|---|---|
| Core vertical slice | 18 |
| LAN channel | 11 |
| Drive sync (mocked) | 10 |
| GUI unit (trip_model, icons) | 19 |
| GUI widget smoke | 5 |
| Persistence — backends | 9 |
| Persistence — idempotency | 6 |
| Persistence — repository | 5 |
| Persistence — restart survival | 4 |
| Persistence — crash boundary | 5 |
| Persistence — differential/integrity/drive/e2e | 9 |
| Live CALL-E (skipped) | 1 |

## Evidence

Receipts bind event, lease, finding, action, and result with SHA-256. Ledger entries chain to the previous receipt hash. Offline verification detects altered components, reordered entries, inserted entries, and deleted middle entries.

```bash
py -m otp.cli demo ack-lease --evidence-dir ./evidence
py -m otp.cli verify ./evidence/<execution_id>.json
py -m otp.cli ledger verify ./evidence/ledger.jsonl
```

## OTP Portable (C89)

**FEATURES MAY DEGRADE. SEMANTICS MUST NOT.**

A minimal C89 implementation of the core pipeline. Compiles with any C compiler on any machine — no Python, no pip, no Qt, no Google.

```
OTP Rich Host                    OTP Portable
Python + Qt + Drive + XLSX        C89 / CLI / headless
        │                                  │
        │          mismo contrato          │
        ▼                                  ▼
   OperationalEvent                OperationalEvent
   Lease                           Lease
   Finding                         Finding
   Sentinel verdict                Sentinel verdict
   ActionRequest                   ActionRequest
   ActionResult                    ActionResult
   Evidence receipt                Evidence receipt
```

### Build

```bash
# Any C compiler works
cc -O2 -o otp otp_portable.c        # gcc/clang/tcc
cl /Fe:otp.exe otp_portable.c       # MSVC
make                                 # Makefile

# Feature flags
cc -DOTP_HAVE_SOCKETS=1 -o otp otp_portable.c    # enable LAN
cc -DOTP_HAVE_SQLITE=1 -o otp otp_portable.c     # enable SQLite
```

### Usage

```bash
./otp doctor              # feature discovery
./otp version             # show version
./otp run dispatch.csv    # process CSV, output receipts
```

### Doctor Output

```
OTP Portable 0.1.0 (C89)
========================================

Compiler ........ C89 compatible
Filesystem ...... YES
SQLite .......... NO
Sockets ......... NO
TLS ............. NO
GUI ............. NO

Profile:
  OTP PORTABLE / HEADLESS

Available:
  [PASS] local pipeline
  [PASS] evidence files
  [DENY] LAN plain transport
  [DENY] Google Drive
  [DENY] desktop GUI
  [DENY] XLSX workbook (use CSV)
```

### Profile Comparison

| Feature | OTP Rich Host | OTP Portable |
|---|---|---|
| Python | Yes | No |
| C compiler | No | Yes |
| GUI (PySide6) | Optional | No |
| Google Drive | Optional | No |
| XLSX workbook | Yes | CSV only |
| SQLite persistence | Yes | Optional |
| LAN transport | Yes | Optional |
| Evidence receipts | Yes | Yes |
| Domain parity | Reference | Identical semantics |

### Files

```
otp_portable/
├── otp_portable.h       # Header: structs, enums, declarations
├── otp_portable.c       # Single-file implementation (~900 lines)
├── Makefile             # Cross-platform build
├── run_tests.sh         # Unix test script
├── run_tests.bat        # Windows test script
└── test_fixtures/       # CSV fixtures for testing
    └── dispatch.csv
```

## Roadmap

- [x] Core pipeline (normalize → evaluate → lease → sentinel → action → channel → receipt)
- [x] RoadStar workbook adapter
- [x] Delivery uncertainty semantics
- [x] LAN channel + Flask relay
- [x] Google Drive sync (OAuth2, SHA-256 evidence backup)
- [x] Persistence layer (SQLite WAL, crash recovery, lifecycle phases)
- [x] GUI control room (PySide6)
- [x] Ephemeral mode for tests
- [x] OTP Portable (C89 single-file, domain parity)
- [ ] CALL-E integration (optional, not a dependency)
- [ ] Shared test fixtures (Python ↔ C domain parity verification)

## License

Internal hackathon project. Not for production use.
