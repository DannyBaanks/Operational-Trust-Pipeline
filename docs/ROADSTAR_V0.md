# RoadStar V0

Official RoadStar materials were downloaded from the participant URLs on 2026-09-10. Their SHA-256 values and source URLs are in `ROADSTAR_SOURCE_EVIDENCE.md`. The workbook contains `Tlorder`, `Dispatch`, `Driver`, `Trucks`, and `Trailers` sheets.

The acknowledgement fixture remains an OTP-owned deterministic control. The workbook adapter maps `Dispatch` and `Driver` rows into normalized events. Source-specific names terminate in that adapter.

Implemented data-backed observations are: ETA later than `DELIVER_BY`, latest status later than `DELIVER_BY`, and an active driver with zero reported remaining HOS hours. There is no observed acknowledgement or document-artifact field in this workbook, so those remain future work.
