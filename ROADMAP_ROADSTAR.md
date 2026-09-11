# RoadStar 100% Roadmap

## Objective

Demonstrate one complete `Dock/HOS Collision` workflow using official RoadStar
data, simulated telemetry, geofencing, detention, Canadian HOS logic, human
intervention, and verifiable OTP evidence.

This roadmap targets complete coverage of the RoadStar challenge deliverables.
It does not claim production readiness, ELD certification, or guaranteed legal
compliance.

## Product Story

```text
SIMULATOR
truck approaching Milton dock
        |
        v
GEOFENCE ENTER
timestamp persisted
        |
        v
dock wait = 1h 40m
HOS remaining = 0h 35m
        |
        v
OTP POLICY
driver will exhaust HOS while detained
        |
        v
SENTINEL
bounded action request
        |
        v
driver/dispatcher ACK
        |
        v
2h threshold crossed
DETENTION BILLING STARTS
        |
        v
receipt + evidence chain
```

The existing OTP core remains intact. New functionality should enter through
RoadStar-specific adapters, policies, simulator outputs, and user interfaces.

## Milestone 0: Honest Baseline

**Estimate:** 2-3 hours  
**Priority:** P0

### Work

- Compile `otp_portable.c` with GCC in Ubuntu CI.
- Run Python-to-C domain parity instead of skipping it on Linux.
- Split CI responsibilities into:
  - Core: Python 3.11 and 3.12.
  - Portable: GCC build and domain parity.
  - Optional integrations: Drive and GUI.
- Update README test counts using current, reproducible results.
- Remove or update the stale `Hackathon Demo (90 seconds)` claim.
- Correct `docs/LIMITATIONS.md`: official RoadStar mapping is implemented;
  acknowledgement data is absent from the workbook.
- Generate a final receipt where `ACKNOWLEDGED` resolves the lease to
  `SATISFIED`.
- Add a `RoadStar requirement -> implementation -> evidence` matrix.

### Definition of Done

- All required CI jobs are green.
- The portable implementation is compiled and executed on Linux.
- README and limitations contain no contradictory claims.
- The final receipt verifies successfully and displays a `SATISFIED` lease.

## Milestone 1: Independent Simulator

**Estimate:** 4-5 hours  
**Priority:** P0

Build a deterministic standalone simulator for this route:

```text
Milton terminal -> Highway 401 -> London facility -> dock queue -> departure
```

### Telemetry

- Simulated timestamp.
- Latitude and longitude.
- Current speed.
- Incremental distance.
- Odometer.
- Duty status.
- Driving hours.
- On-duty hours.
- Elapsed shift hours.
- Cycle hours.
- Highway slowdown event.
- Dock waiting event.

### Controls

- Start.
- Pause.
- Reset.
- Simulation speeds: `1x`, `10x`, and `60x`.
- Scenario selection.

### Constraints

- Keep `roadstar_simulator.py` independent from the GUI.
- Use a fixed seed and deterministic scenario clock.
- Publish telemetry through HTTP/SSE, polling JSON, or the smallest compatible
  mechanism already supported by the application.
- Convert simulator output into `OperationalEvent` through an adapter.

### Definition of Done

- One documented command starts the simulator.
- The same seed produces the same event sequence.
- The dashboard receives live updates.
- Tests verify monotonic distance, odometer, time, and HOS progression.
- The simulator runs without the desktop GUI.

## Milestone 2: Southern Ontario Map

**Estimate:** 5-6 hours  
**Priority:** P0

### Surface

- Interactive Southern Ontario map.
- OpenStreetMap street layer.
- Satellite layer toggle.
- Truck markers.
- Milton, London, and Kitchener facilities.
- Historical route breadcrumbs.
- Milton-to-London route.
- Current speed.
- Leg distance.
- Odometer.
- Last telemetry timestamp.
- HOS status.
- Dock status.

### Scope Guard

Do not build:

- A general route solver.
- General-purpose geocoding.
- Global fleet optimization.
- A GIS editor.
- New infrastructure unrelated to the demo flow.

### Definition of Done

- The truck moves visibly as telemetry arrives.
- Breadcrumbs remain visible behind the truck.
- Satellite mode works.
- Speed and distance update from simulator data.
- The page preserves useful operational state if map tiles fail.
- The view covers the Southern Ontario region specified by the brief.

## Milestone 3: Geofence and Detention

**Estimate:** 4-5 hours  
**Priority:** P0

### Minimum Model

- Facility ID.
- Facility center and radius.
- `ENTERED` event.
- `ARRIVED_AT_DOCK` event.
- `DEPARTED` event.
- Arrival timestamp.
- Departure timestamp.
- Dock wait duration.
- Two-hour free threshold.
- Billable duration.
- Configurable detention rate.
- Estimated detention charge.

### Invariants

- The first outside-to-inside transition records one entry.
- Remaining inside does not create duplicate entries.
- The first inside-to-outside transition records one departure.
- Reprocessing the same telemetry event is idempotent.
- Waiting less than or equal to two hours produces no billable detention.
- Only time beyond two hours is billable.
- Timestamps are persisted before external action requests.

### Required Boundary Tests

- `1:59:59` -> no detention.
- `2:00:00` -> no excess detention.
- `2:00:01` -> detention active.
- GPS jitter near the boundary -> no duplicate transitions.
- Re-entry -> a new, explicitly identified visit.
- Restart during dock wait -> duration remains recoverable.

### Definition of Done

- Arrival and departure appear in the dashboard.
- SQLite contains exact timestamps.
- Detention is calculated automatically.
- The detention event produces an OTP receipt.
- The UI displays free time, excess time, and estimated charge.

## Milestone 4: Canadian HOS Rules

**Estimate:** 5-6 hours  
**Priority:** P0

Extend `HosCapacityPolicy`; do not replace it.

### Rules

- 13-hour driving limit.
- 14-hour on-duty limit.
- 16-hour elapsed shift window.
- 10 hours of daily off-duty time.
- Eight-hour consecutive core rest.
- Cycle 1: 70 on-duty hours in 7 days.
- Cycle 2: 120 on-duty hours in 14 days.

### Outcomes

- `PASS`.
- `AT_RISK`.
- `FAIL`.
- `UNKNOWN` when required inputs are absent.

### Killer Policy

Implement `DockHosCollisionPolicy`:

```text
estimated dock release > earliest HOS limit
    -> HOS_EXHAUSTION_DURING_DETENTION
```

The finding must state:

- Which HOS limit will be exhausted.
- When exhaustion is expected.
- How much time remains.
- Which bounded action is recommended.
- Which evidence supports the conclusion.

### Claim Boundary

Do not claim:

- ELD certification.
- Transport Canada certification.
- Guaranteed legal compliance.

Use this claim instead:

> Decision support modeled from the Canadian South-of-60 HOS limits provided
> in the RoadStar challenge brief.

### Definition of Done

- Unit tests cover every modeled limit.
- Tests cover values immediately before, at, and after each boundary.
- Missing required data produces `UNKNOWN`, never `PASS`.
- The dock scenario produces `HOS_EXHAUSTION_DURING_DETENTION`.
- Sentinel requests human action rather than reassigning automatically.

## Milestone 5: Driver Interface

**Estimate:** 3-4 hours  
**Priority:** P0

Extend the existing responsive LAN receiver instead of creating a separate
mobile application.

### Display

- Current load.
- Origin and destination.
- Appointment time.
- Route map.
- Duty status.
- Remaining driving and on-duty time.
- Current dock status.

### Actions

- `ACCEPT LOAD`.
- `REJECT LOAD` with reason.
- `ACKNOWLEDGE`.
- `ARRIVED`.
- `DEPARTED`.

Every action must:

- Carry a request identity.
- Be idempotent.
- Update operational state.
- Produce an `ActionResult`.
- Resolve or preserve the lease correctly.
- Reach an evidence receipt.

### Definition of Done

- The interface works from a phone over LAN.
- It requires no mobile installation.
- Load acceptance appears in dispatch.
- Acknowledgement produces lease state `SATISFIED`.
- Refreshing or retrying does not duplicate actions.

## Milestone 6: Minimal Load Matching

**Estimate:** 3-4 hours  
**Priority:** P1

Implement an explainable deterministic ranking, not an AI model or general
optimization solver.

### Demo Case

- Truck completes a Milton-to-London load.
- Search for a compatible London-to-Kitchener load.
- Reduce empty/deadhead distance.

### Filters

- Truck availability.
- Trailer compatibility.
- Weight/capacity compatibility.
- Pickup window feasibility.
- Sufficient HOS.
- Distance to pickup.

### Ranking

```text
score =
    deadhead_km
    + HOS risk penalty
    + appointment risk penalty
    + equipment mismatch hard rejection
```

### Output

- Top candidates.
- Current deadhead distance.
- Estimated matched deadhead distance.
- Kilometers saved.
- Ranking reasons.
- `UNKNOWN` when critical inputs are absent.

### Definition of Done

- Matching uses loads from the official workbook.
- London-to-Kitchener appears as a verifiable candidate when compatible.
- Results are deterministic.
- Every rejection carries a reason code.
- The dispatcher chooses; OTP does not assign automatically.

## Milestone 7: Integrated Vertical Slice

**Estimate:** 3-4 hours  
**Priority:** P0

This is the only workflow that must be flawless:

```text
1. Simulator starts the truck in Milton.
2. Dashboard displays route and breadcrumbs.
3. Highway 401 slowdown reduces speed.
4. Truck enters the London geofence.
5. Arrival timestamp is persisted.
6. Dock waiting begins.
7. Remaining HOS falls.
8. OTP predicts HOS exhaustion during detention.
9. Sentinel issues a bounded acknowledgement request.
10. Driver acknowledges from a phone.
11. Lease changes to SATISFIED.
12. The two-hour threshold is crossed.
13. Detention billing begins.
14. Truck exits the geofence.
15. Departure timestamp is persisted.
16. OTP calculates final detention.
17. Load matcher proposes London-to-Kitchener.
18. The evidence receipt verifies offline.
```

### Definition of Done

- The entire scenario succeeds twice consecutively.
- No file must be edited manually during the demo.
- Reset restores the initial scenario.
- Mock behavior is never presented as live production infrastructure.
- Every important state transition produces evidence.
- The rendered viewer and verifier consume the same embedded receipt object.

## Milestone 8: Submission Package

**Estimate:** 5-7 hours  
**Priority:** P0

### Demo Video

**Target duration:** 3:20-3:45. The official requirement is 3-5 minutes.

```text
0:00-0:20  Industry problem and financial cost
0:20-0:45  Official RoadStar workbook and dashboard
0:45-1:20  Simulator, map, breadcrumbs, and highway slowdown
1:20-2:05  Geofence, detention, and Dock/HOS Collision
2:05-2:35  Driver ACK and SATISFIED lease
2:35-2:55  London-to-Kitchener load match
2:55-3:20  Offline receipt verification and tamper detection
3:20-3:35  Impact and final message
```

The video must show the working product. Synthetic slides may support the
narrative but must not replace the real end-to-end demonstration.

### Final Presentation

Prepare a 10-15 minute presentation covering:

1. Industry problem.
2. Financial impact.
3. Product overview.
4. Live or recorded product demonstration.
5. Dock/HOS Collision.
6. Architecture.
7. Use of official RoadStar data.
8. Trust and evidence model.
9. Expected operational impact.
10. Honest limitations.

### Submission Page

Include:

- One-line product statement.
- Problem.
- Solution.
- How it was built.
- Use of RoadStar resources.
- Edge case discovered.
- Accomplishments.
- Future work.
- Demo URL.
- GitHub URL.
- Three-to-five-minute video.

### Definition of Done

- Video duration is between 3 and 5 minutes.
- Demo URL works in an incognito browser session.
- Repository is accessible to judges.
- Required CI jobs are green without hiding core or parity tests.
- Submission is sent before September 13, 2026 at 12:00 PM EDT.
- Submission confirmation is preserved.

## Critical Schedule

### September 11

- Complete Milestone 0.
- Complete Milestone 1.
- Complete Milestone 3.
- Run the first vertical slice without final map polish.

### September 12 Morning

- Complete Milestone 2.
- Complete Milestone 4.
- Complete Milestone 5.

### September 12 Afternoon

- Complete Milestone 6.
- Complete Milestone 7.
- Fix integration bugs only.

### September 12 Evening

- Feature freeze.
- Capture the final demonstration.
- Render the 3-5 minute video.
- Update README and evidence.
- Prepare the submission and presentation.

### September 13

- Run a clean-machine smoke test.
- Verify every public URL.
- Upload the final video.
- Submit before 12:00 PM EDT.
- Do not rely on a conflicting later deadline.

## Cut Order

If time runs short, remove scope in this order:

1. CALL-E.
2. Drive during the live demo.
3. C89 from the video, while preserving its CI verification.
4. Additional simulator scenarios.
5. Top-three matching results; retain the best candidate only.
6. Cycle 2 visualization, while preserving its tests.
7. Satellite-layer polish.

Never cut:

- Independent simulator.
- Geofence transitions.
- Detention after two hours.
- HOS 13-hour and 14-hour rules.
- Dock/HOS Collision.
- Driver acceptance and acknowledgement.
- Final internally consistent receipt.
- A submission video between 3 and 5 minutes.

## Target Judging Score

| Criterion | Target | Evidence |
|---|---:|---|
| Industry Impact and Relevance | 5/5 | Detention revenue, dispatcher time, deadhead reduction |
| Innovation and Creativity | 5/5 | Dock/HOS Collision plus bounded trust and evidence |
| Technical Execution and Quality | 5/5 | Determinism, persistence, recovery, CI, receipts |
| Use of Provided Data and APIs | 4-5/5 | Official workbook, mapping, and simulator |
| Presentation and Demo Quality | 5/5 | One clear end-to-end story in approximately 3:30 |

## Feature Freeze Rule

After these surfaces are complete:

```text
Simulator
Map
Geofence/Detention
HOS Collision
Driver UI
Minimal Load Matching
```

enter feature freeze.

Do not add a chatbot, LLM dispatcher, blockchain, general optimizer, new
microservice architecture, or another speculative feature. Spend the remaining
time on integration, tests, evidence, documentation, video, and submission.
