# Provenance

Audited 2026-09-10 from local checkouts by repository content and configured remotes.

| Material | Local path | HEAD | Remote |
|---|---|---|---|
| Trustworthy Document Pipeline | `C:\Development\ISyCo Git\trustworthy-document-pipeline` | `42eba3e74bfbef416e4f588e4f8f874a2e6a98fd` | `https://github.com/DannyBaanks/TrustworthyDocumentPipeline.git` |
| ISyCoCALL-e | `C:\Development\ISyCo Git\ISyCo CALL-E` | `e25cb3794dd0a37dea5b8823428e3706cdcb30e3` | `https://github.com/DannyBaanks/ISyCoCALL-e.git` |
| call-e-integrations | `C:\Development\ISyCo Git\call-e-integrations` | `27b678b06b5dc2b2d0e1fde3a43ddcbcb870021a` | `origin https://github.com/DannyBaanks/call-e-integrations`; `upstream https://github.com/CALLE-AI/call-e-integrations` |

The initial local audit found no RoadStar material. On 2026-09-10, participant-provided RoadStar workbook, brief, and presentation files were downloaded into `fixtures/roadstar/`; their URLs and SHA-256 values are recorded in `ROADSTAR_SOURCE_EVIDENCE.md`. `ack_assignment.json` remains an OTP-owned deterministic control fixture, not official RoadStar data.

OTP adopts patterns, not copied implementation: canonical SHA-256 records, chained ledger verification, provider ports, explicit uncertainty, and a documented tail-truncation limit. The CALL-E boundary delegates call authority to ISyCoCALL-e rather than reproducing its authority model.
