# OTP GUI — Control Room

Dispatcher console for the Operational Trust Pipeline. Minimal, industrial, designed for a 60-90 second hackathon demo.

## Running

```bash
# Full GUI (requires PySide6)
otp gui

# CLI fallback (no GUI)
otp demo ack-lease
```

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Archivo    Ver    Ayuda                     Operational Trust  │
├──────────────────────────────────────────────────────────────────┤
│  CRITICAL 3  AT RISK 8  WAITING 5  UNCERTAIN 2  RESOLVED 21   │
├──────────────────────────────────────────────────────────────────┤
│  Trips table (sortable by ID, ETA, DELTA, STATE, ACK)          │
├──────────────────────────────────────────────────────────────────┤
│  Detail: WHY THIS FIRED | ACTION | STATUS | EVIDENCE           │
└──────────────────────────────────────────────────────────────────┘
```

## Trip States

| State | Color | Meaning |
|---|---|---|
| CRITICAL | Red | Overdue + no ack |
| AT RISK | Orange | Will miss deadline soon |
| WAITING ACK | Orange | Request sent, no response |
| DELIVERY UNCERTAIN | Gray | Provider accepted, no proof |
| ON TIME | Dim | Within window |
| RESOLVED | Green | Acknowledged, verified |
| BLOCKED | Gray | Sentinel denied |
| UNKNOWN | Gray | Missing data |

## Keyboard

| Key | Action |
|---|---|
| Enter | Request ACK for selected trip |
| F5 | Refresh all trips |
| Ctrl+O | Open evidence file |
| Ctrl+S | Save receipt |
| Ctrl+L | Request Acknowledgement |
| Ctrl+F | Focus search |

## 90-Second Demo Flow

1. Window opens maximized. Top bar shows "CRITICAL 3 AT RISK 8".
2. Table shows trips sorted by delta. Row 28471 is red: +27 min.
3. Click 28471. Detail panel shows: ETA 14:32 > DELIVER_BY 14:05.
4. Click "Request ACK". Modal opens with local URL.
5. Open URL on phone. Tap ACKNOWLEDGE.
6. Modal auto-updates: "ACKNOWLEDGED". Close modal.
7. Main window: Trip 28471 shows RESOLVED. Receipt: 8f31...a920 verified.

## Files

| File | Purpose |
|---|---|
| `gui/__init__.py` | Entry point |
| `gui/main_window.py` | QMainWindow + menus + splitter |
| `gui/trip_table.py` | Sortable QTableView |
| `gui/detail_panel.py` | Bottom panel (WHY/ACTION/STATUS/EVIDENCE) |
| `gui/lan_modal.py` | Request acknowledgement dialog |
| `gui/trip_model.py` | TripItem + state computation |
| `gui/workers.py` | Background threads |
| `gui/styles.py` | Dark theme |
| `gui/icons.py` | State indicator icons |
