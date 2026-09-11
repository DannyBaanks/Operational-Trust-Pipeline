# Threat Model

Receipts bind canonical event, lease, finding, action, and result representations with SHA-256. Ledger entries bind to the preceding receipt hash. Offline verification detects altered components, altered receipts, reordered entries, inserted entries, and deleted middle entries.

It does not replay a provider, prove a human received a message, prove external delivery, or detect a deleted ledger tail without a separately retained external head hash. This is tamper-evident evidence, not tamper-proof storage.

The Sentinel fails closed: a finding alone cannot call a provider; missing required data requires review; a denied authority context causes zero provider calls.

## Delivery-uncertainty invariants

1. `provider_accepted=True` alone does not satisfy a lease. Only `recipient_acknowledged()` (which requires `acknowledged=True` AND `delivery != "NOT_DEMONSTRATED"`) transitions a lease to `SATISFIED`.
2. `NO ANSWER` / `ByCallee` / 0s duration from CALL-E maps to `delivery=UNKNOWN`, `reached_ringing=UNKNOWN`. This is NOT proof the handset rang. The five uncertainty fields are included in every evidence receipt.
3. The Sentinel cannot upgrade `UNKNOWN` delivery to `KNOWN`. Only the channel adapter, with direct access to provider signals, can set `delivery=KNOWN`.
4. A receipt with `delivery=UNKNOWN` is a valid negative result. It is not a failure of the pipeline; it is the pipeline correctly refusing to overstate what it knows.
