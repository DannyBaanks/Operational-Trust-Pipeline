# Contracts

`OperationalEvent` contains normalized identifiers, timing, payload, and canonical payload hash. `Lease` is a deterministic, first-class acknowledgement obligation. `Finding` uses stable reason codes. `ActionRequest` is channel-neutral and contains no phone, SIP, radio, Twilio, or CALL-E type.

`ChannelProvider.send(ActionRequest) -> ActionResult` is the only channel port. Results use bounded OTP statuses; provider-native states are retained only as bounded error evidence.

Missing deadline data yields `UNKNOWN` and `NEEDS_REVIEW`; it never yields a false healthy outcome.
