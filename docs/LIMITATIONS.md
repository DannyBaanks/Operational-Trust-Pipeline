# Limitations

- Only the fixture-backed acknowledgement policy is IMPLEMENTED.
- Official RoadStar workbook mapping is implemented and covered by adapter tests.
- The workbook does not contain observed acknowledgement or dock-arrival data;
  those remain simulator/demo inputs rather than historical workbook facts.
- Missing-artifact and stale-operation scenarios are NOT_DEMONSTRATED.
- CALL-E live execution is wired at a boundary but LIVE_NOT_TESTED; no real call was attempted.
- A mock acknowledgement is a provider response, not proof of a human acknowledgement.
- Ledger verification has the documented unanchored tail-truncation limitation.
