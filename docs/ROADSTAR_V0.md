# RoadStar V0

No official RoadStar data or participant resource was present locally at implementation time. Therefore OTP does not claim a production RoadStar schema.

The checked-in fixture supports only acknowledgement leases and has observed fixture fields: `assignment_id`, `trip_id`, `driver_ref`, `assigned_at`, `ack_due_at`, `acknowledged_at`, and `contact_ref`. `RoadStarAdapter` maps them to generic assignment and acknowledgement concepts.

Missing required artifact and stale-operation policies are future work, not fabricated scenarios. They require an observed RoadStar schema and semantics.
