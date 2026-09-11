# Architecture

`RoadStarAdapter -> OperationalEvent -> AckLeasePolicy -> Sentinel -> ActionRequest -> ChannelProvider -> ActionResult -> EvidenceReceipt -> Ledger`

The domain layer has no RoadStar or CALL-E imports. `RoadStarAdapter` owns fixture-specific names. `CalleChannel` is an optional outer adapter which transforms the generic request into `isyco_calle.domain.contract.PhoneCallRequest` only when live execution has been deliberately enabled and a CALL-E capability has been supplied.

The Sentinel authorizes crossing the OTP action-request boundary only. It does not grant phone capability authority. CALL-E independently evaluates its authority before dispatch.
