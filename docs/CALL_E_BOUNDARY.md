# CALL-E Boundary

`CalleChannel` is a thin optional adapter. Its default is `live=False`, yielding `NOT_DEMONSTRATED` without importing SDK types or placing a call. A live path requires an explicitly supplied ISyCoCALL-e `PhoneCallCapability`, resolved phone target metadata, and CALL-E's own authority decision.

OTP deciding `ACTION_REQUESTED` means only that operational policy permits requesting communication. It does not mean the phone capability is authorized. CALL-E's capability evaluates technical availability, explicit grant, policy allowance, and execution verification. A CALL-E mock must never be described as live.

No live credential inspection or phone-call execution is performed by this project.
