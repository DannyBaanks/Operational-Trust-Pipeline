# Threat Model

Receipts bind canonical event, lease, finding, action, and result representations with SHA-256. Ledger entries bind to the preceding receipt hash. Offline verification detects altered components, altered receipts, reordered entries, inserted entries, and deleted middle entries.

It does not replay a provider, prove a human received a message, prove external delivery, or detect a deleted ledger tail without a separately retained external head hash. This is tamper-evident evidence, not tamper-proof storage.

The Sentinel fails closed: a finding alone cannot call a provider; missing required data requires review; a denied authority context causes zero provider calls.
