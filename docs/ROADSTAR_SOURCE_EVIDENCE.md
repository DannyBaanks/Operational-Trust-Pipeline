# RoadStar Source Evidence

Downloaded 2026-09-10 from participant-provided URLs. These raw materials are inputs, not claims that OTP has validated their business semantics.

| File | URL | SHA-256 |
|---|---|---|
| `Hackathon_Data.xlsx` | `https://roadstarhackathon.com/uploads/documents/1788655393951_Hackathon_Data.xlsx` | `8ee7e47e545bcda92aaa8ba71dae4b472bdf2d7db950ade20c1089ed0dd4b19c` |
| `Presentation1.pptx` | `https://roadstarhackathon.com/uploads/documents/1788655471571_Presentation1.pptx` | `d7fd9c389b4afb297acacb1a8261ae220a22bd73ac2c2e68cd941270a45878f5` |
| `Hackathon_Project_Brief.pdf` | `https://roadstarhackathon.com/uploads/documents/1788654151601_Hackathon_Project_Brief.pdf` | `ebb0c998159530e0be895868717c1828f863846705665e788cbfd13b90c58e37` |

Observed workbook facts: `Dispatch` has 10,479 data rows after its repeated header, and exposes `LS_EXPECTED_DATE`, `DELIVER_BY`, `LS_LAST_FB_STATUS_DATE`, `REMAINING_HOURS`, and `HOS_VIOLATION_AT`; `Driver` exposes `REMAINING_HOURS`, `STATUS`, `HOURS_UPDATED`, `CURRENT_TRIP`, and `EMAIL`. Profiling found 12 rows with expected date later than `DELIVER_BY`, 4,272 rows with latest feedback status later than `DELIVER_BY`, and 11 driver rows with zero remaining hours. These are data observations, not claims of regulatory breach.
