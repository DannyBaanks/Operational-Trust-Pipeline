# Operational Trust Pipeline

Operational Trust Pipeline turns operational state into bounded, verifiable human-action requests without coupling the decision layer to a data source or communication provider.

`source -> normalize -> evaluate -> lease/policy -> Sentinel -> action request -> provider -> acknowledgement -> receipt`

The first demonstrated composition is `RoadStar-like fixture -> OTP -> mock channel`. CALL-E is wired as an optional channel boundary but is not executed. RoadStar is an adapter; CALL-E is an adapter; neither is required by the core.

```powershell
py -m pytest -q
py -m otp.cli demo ack-lease
```

The demo is offline and writes no receipt unless `--evidence-dir` is supplied. See `docs/LIMITATIONS.md` before treating this prototype as evidence of a live operational integration.
