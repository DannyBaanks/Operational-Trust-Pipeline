/*
 * otp_portable.h — OTP Portable Core
 *
 * Minimal C89/C90 implementation of the Operational Trust Pipeline.
 * Compiles with: cc otp_portable.c -o otp
 *
 * FEATURES MAY DEGRADE. SEMANTICS MUST NOT.
 *
 * Feature flags (enable at compile time):
 *   -DOTP_HAVE_SQLITE=1    SQLite persistence
 *   -DOTP_HAVE_SOCKETS=1   LAN transport
 *   -DOTP_HAVE_TLS=1       TLS support
 */

#ifndef OTP_PORTABLE_H
#define OTP_PORTABLE_H

/* ------------------------------------------------------------------ */
/*  VERSION                                                            */
/* ------------------------------------------------------------------ */

#define OTP_VERSION       "0.1.0"
#define OTP_VERSION_MAJOR 0
#define OTP_VERSION_MINOR 1
#define OTP_VERSION_PATCH 0

/* ------------------------------------------------------------------ */
/*  FEATURE FLAGS (default OFF, enable via compile flags)              */
/* ------------------------------------------------------------------ */

#ifndef OTP_HAVE_SQLITE
#define OTP_HAVE_SQLITE 0
#endif

#ifndef OTP_HAVE_SOCKETS
#define OTP_HAVE_SOCKETS 0
#endif

#ifndef OTP_HAVE_TLS
#define OTP_HAVE_TLS 0
#endif

/* ------------------------------------------------------------------ */
/*  C89 COMPATIBILITY                                                  */
/* ------------------------------------------------------------------ */

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 199901L
#define OTP_C99 1
#else
#define OTP_C99 0
#endif

/* ------------------------------------------------------------------ */
/*  FIXED-WIDTH BASICS (C89 fallbacks)                                 */
/* ------------------------------------------------------------------ */

#include <stddef.h>
#include <limits.h>

typedef unsigned char  otp_u8;
typedef unsigned int   otp_u32;

/* 64-bit type: use compiler built-in if available, else struct */
#if defined(__GNUC__) || defined(_MSC_VER) || (defined(__STDC_VERSION__) && __STDC_VERSION__ >= 199901L)
typedef unsigned long long otp_u64;
#else
typedef struct { otp_u32 lo; otp_u32 hi; } otp_u64;
#endif

/* ------------------------------------------------------------------ */
/*  ENUMS                                                              */
/* ------------------------------------------------------------------ */

typedef enum {
    LEASE_OPEN       = 0,
    LEASE_SATISFIED  = 1,
    LEASE_EXPIRED    = 2,
    LEASE_CANCELLED  = 3,
    LEASE_UNKNOWN    = 4
} OtpLeaseState;

typedef enum {
    FINDING_PASS     = 0,
    FINDING_FAIL     = 1,
    FINDING_UNKNOWN  = 2
} OtpFindingStatus;

typedef enum {
    VERDICT_NO_ACTION        = 0,
    VERDICT_ACTION_REQUESTED = 1,
    VERDICT_BLOCKED          = 2,
    VERDICT_NEEDS_REVIEW     = 3,
    VERDICT_NOT_DEMONSTRATED = 4
} OtpSentinelVerdict;

typedef enum {
    ACTION_ACKNOWLEDGED        = 0,
    ACTION_REJECTED            = 1,
    ACTION_FAILED              = 2,
    ACTION_PROVIDER_UNAVAIL    = 3,
    ACTION_NOT_DEMONSTRATED    = 4
} OtpActionStatus;

/* ------------------------------------------------------------------ */
/*  SIZE LIMITS                                                        */
/* ------------------------------------------------------------------ */

#define OTP_MAX_ID       64
#define OTP_MAX_STR     256
#define OTP_MAX_PAYLOAD 4096
#define OTP_MAX_FIELDS     8
#define OTP_MAX_TIMESTAMP  40

/* ------------------------------------------------------------------ */
/*  CORE STRUCTS                                                       */
/* ------------------------------------------------------------------ */

typedef struct {
    char event_id[OTP_MAX_ID];
    char schema_version[OTP_MAX_STR];
    char source[OTP_MAX_STR];
    char source_event_type[OTP_MAX_STR];
    char source_ref[OTP_MAX_STR];
    char entity_type[OTP_MAX_STR];
    char entity_id[OTP_MAX_STR];
    char observed_at[OTP_MAX_TIMESTAMP];
    /* Payload fields — flattened for C89 simplicity */
    char payload_trip_ref[OTP_MAX_STR];
    char payload_leg_ref[OTP_MAX_STR];
    char payload_expected_at[OTP_MAX_TIMESTAMP];
    char payload_due_at[OTP_MAX_TIMESTAMP];
    char payload_latest_state_at[OTP_MAX_TIMESTAMP];
    char payload_operation_status[OTP_MAX_STR];
    char payload_remaining_hours[OTP_MAX_STR];
    char payload_contact_ref[OTP_MAX_STR];
    char payload_ack_due_at[OTP_MAX_TIMESTAMP];
    char payload_acknowledged_at[OTP_MAX_TIMESTAMP];
    char payload_assignment_ref[OTP_MAX_STR];
    char payload_assignee_ref[OTP_MAX_STR];
    char payload_sha256[65];
} OtpEvent;

typedef struct {
    char lease_id[OTP_MAX_ID];
    char kind[OTP_MAX_STR];
    char subject_ref[OTP_MAX_STR];
    char opened_at[OTP_MAX_TIMESTAMP];
    char due_at[OTP_MAX_TIMESTAMP];
    OtpLeaseState state;
    char required_condition[OTP_MAX_STR];
    char resolution[OTP_MAX_STR];
    char closed_at[OTP_MAX_TIMESTAMP];
} OtpLease;

typedef struct {
    char finding_id[OTP_MAX_ID];
    char rule_id[OTP_MAX_STR];
    OtpFindingStatus status;
    char severity[OTP_MAX_STR];
    char subject_ref[OTP_MAX_STR];
    char reason_code[OTP_MAX_STR];
    char reason[OTP_MAX_STR];
    int  action_recommended;
} OtpFinding;

typedef struct {
    char action_id[OTP_MAX_ID];
    char action_type[OTP_MAX_STR];
    char target_ref[OTP_MAX_STR];
    char channel[OTP_MAX_STR];
    char objective[OTP_MAX_STR];
    char message[OTP_MAX_STR];
    int  require_ack;
    char urgency[OTP_MAX_STR];
    char source_finding_id[OTP_MAX_ID];
} OtpActionRequest;

typedef struct {
    char action_id[OTP_MAX_ID];
    char provider[OTP_MAX_STR];
    char provider_ref[OTP_MAX_STR];
    OtpActionStatus status;
    int  acknowledged;
    char response[OTP_MAX_STR];
    char started_at[OTP_MAX_TIMESTAMP];
    char completed_at[OTP_MAX_TIMESTAMP];
    char error_code[OTP_MAX_STR];
    int  provider_accepted;
    char delivery[OTP_MAX_STR];
    char reached_ringing[OTP_MAX_STR];
    char terminal_cause[OTP_MAX_STR];
    char retry_safe[OTP_MAX_STR];
} OtpActionResult;

/* ------------------------------------------------------------------ */
/*  EVIDENCE                                                           */
/* ------------------------------------------------------------------ */

typedef struct {
    char schema_version[OTP_MAX_STR];
    char execution_id[OTP_MAX_ID];
    char source_adapter[OTP_MAX_STR];
    char policy_version[OTP_MAX_STR];
    char channel_adapter[OTP_MAX_STR];
    int  verdict;
    /* Component SHA-256s */
    char sha256_event[65];
    char sha256_lease[65];
    char sha256_finding[65];
    char sha256_action[65];
    char sha256_result[65];
    char previous_receipt_sha256[65];
    char receipt_sha256[65];
} OtpReceipt;

/* ------------------------------------------------------------------ */
/*  CLOCK                                                              */
/* ------------------------------------------------------------------ */

/* Function pointer type for clock abstraction */
typedef void (*otp_clock_now_fn)(char *buf, int bufsize);

/* System clock: returns current UTC time in ISO 8601 */
void otp_clock_system(char *buf, int bufsize);

/* Fixed clock: returns a predetermined time (for tests) */
typedef struct {
    char frozen_time[OTP_MAX_TIMESTAMP];
} OtpFixedClock;

void otp_clock_fixed(const OtpFixedClock *clk, char *buf, int bufsize);

/* ------------------------------------------------------------------ */
/*  CANONICAL / SHA-256                                                */
/* ------------------------------------------------------------------ */

/* SHA-256 hash: 32 bytes raw, 65 bytes hex string (with null) */
void otp_sha256_raw(const void *data, size_t len, otp_u8 out[32]);
void otp_sha256_hex(const void *data, size_t len, char out[65]);

/* Canonical JSON serialization (sorted keys, compact, no whitespace) */
/* Writes canonical form of a simple key-value map to buf.             */
/* keys and values are string arrays. n is number of pairs.            */
int otp_canonical_json(char *buf, int bufsize,
                       const char *keys[], const char *vals[], int n);

/* Stable ID: prefix_sha256(value)[:20] */
void otp_stable_id(char *out, int outsize,
                   const char *prefix, const char *value);

/* ------------------------------------------------------------------ */
/*  DOMAIN: constructors                                               */
/* ------------------------------------------------------------------ */

void otp_event_init(OtpEvent *e);
void otp_event_compute_id(OtpEvent *e);

void otp_lease_init(OtpLease *l);
void otp_lease_compute_id(OtpLease *l);

void otp_finding_init(OtpFinding *f);
void otp_finding_compute_id(OtpFinding *f);

void otp_action_request_init(OtpActionRequest *a);
void otp_action_request_compute_id(OtpActionRequest *a);

/* ------------------------------------------------------------------ */
/*  DOMAIN: predicates                                                 */
/* ------------------------------------------------------------------ */

/* The ONLY predicate that satisfies a lease. */
int otp_recipient_acknowledged(const OtpActionResult *r);

/* ------------------------------------------------------------------ */
/*  PIPELINE: pure functions                                           */
/* ------------------------------------------------------------------ */

/* AckLeasePolicy: 4 branches */
void otp_ack_lease_policy_evaluate(
    const OtpEvent *event,
    const OtpLease *lease,
    otp_clock_now_fn clock,
    OtpFinding *out
);

/* make_ack_lease: derive lease from event */
void otp_make_ack_lease(
    const OtpEvent *event,
    otp_clock_now_fn clock,
    OtpLease *out
);

/* Sentinel: deny-by-default gate */
OtpSentinelVerdict otp_sentinel(
    const OtpFinding *finding,
    int communication_allowed
);

/* request_for: build action request from finding + event */
void otp_request_for(
    const OtpFinding *finding,
    const OtpEvent *event,
    const char *channel,
    OtpActionRequest *out
);

/* Full ack-lease evaluation in one call */
void otp_evaluate_ack(
    const OtpEvent *event,
    OtpLease *lease,
    otp_clock_now_fn clock,
    int communication_allowed,
    OtpFinding *finding,
    OtpSentinelVerdict *verdict,
    OtpActionRequest *action
);

/* Resolve lease after result */
void otp_resolve_ack_lease(
    OtpLease *lease,
    const OtpFinding *finding,
    const OtpActionResult *result
);

/* Execution ID */
void otp_execution_id(char *out, int outsize,
                      const OtpEvent *event,
                      const OtpLease *lease,
                      const char *policy_version);

/* ------------------------------------------------------------------ */
/*  EVIDENCE: receipts and ledger                                      */
/* ------------------------------------------------------------------ */

/* Build receipt from a completed run */
void otp_make_receipt(
    const OtpEvent *event,
    const OtpLease *lease,
    const OtpFinding *finding,
    const OtpActionRequest *action,
    const OtpActionResult *result,
    const char *execution_id,
    const char *source_adapter,
    const char *policy_version,
    const char *channel_adapter,
    int verdict,
    const char *previous_receipt_sha256,
    OtpReceipt *out
);

/* Serialize receipt to JSON (writes to buf, returns bytes written) */
int otp_receipt_to_json(char *buf, int bufsize, const OtpReceipt *r);

/* Append receipt to ledger file */
int otp_append_ledger(const char *path, const OtpReceipt *r);

/* ------------------------------------------------------------------ */
/*  ADAPTER: RoadStar (CSV mode)                                       */
/* ------------------------------------------------------------------ */

typedef struct {
    /* Raw CSV fields */
    char trip_number[OTP_MAX_STR];
    char leg_id[OTP_MAX_STR];
    char expected_date[OTP_MAX_STR];
    char deliver_by[OTP_MAX_STR];
    char last_status_date[OTP_MAX_STR];
    char status[OTP_MAX_STR];
    /* Driver fields */
    char driver_id[OTP_MAX_STR];
    char remaining_hours[OTP_MAX_STR];
    char driver_status[OTP_MAX_STR];
    char hours_updated[OTP_MAX_STR];
    char email[OTP_MAX_STR];
} OtpRawRecord;

/* Normalize a dispatch record */
void otp_normalize_dispatch(const OtpRawRecord *raw, OtpEvent *out);

/* Normalize a driver record */
void otp_normalize_driver(const OtpRawRecord *raw, OtpEvent *out);

/* ------------------------------------------------------------------ */
/*  JSON (minimal parser for fixtures)                                 */
/* ------------------------------------------------------------------ */

/* Parse a JSON string and extract a value by key.
 * Returns 1 if found, 0 if not. Handles string/number/bool/null values.
 * For nested objects, out_buf receives the raw JSON substring. */
int json_get_string(const char *json, const char *key, char *out, int outsize);
int json_get_int(const char *json, const char *key, int *out);
int json_get_bool(const char *json, const char *key, int *out);

/* Extract a nested object by key (raw JSON substring) */
int json_get_object(const char *json, const char *key, char *out, int outsize);

/* Parse a JSON event file into OtpEvent */
int otp_event_from_json(const char *json, OtpEvent *out);

/* Serialize event to JSON */
int otp_event_to_json(char *buf, int bufsize, const OtpEvent *e);

/* Serialize finding to JSON */
int otp_finding_to_json(char *buf, int bufsize, const OtpFinding *f);

/* ------------------------------------------------------------------ */
/*  CLI                                                                */
/* ------------------------------------------------------------------ */

/* Run the pipeline on a CSV file, output to stdout */
int otp_run_csv(const char *csv_path, int communication_allowed);

/* Verify parity: read JSON fixture, run pipeline, compare */
int otp_verify_parity(const char *fixture_path);

/* Doctor: show feature discovery */
void otp_doctor(void);

/* ------------------------------------------------------------------ */
/*  UTILITIES                                                          */
/* ------------------------------------------------------------------ */

/* Copy at most n-1 chars, always null-terminate */
void otp_str_copy(char *dst, const char *src, int n);

/* Compare strings */
int otp_str_eq(const char *a, const char *b);

/* Is string empty or null? */
int otp_str_empty(const char *s);

/* Current UTC time as ISO 8601 (platform-specific impl) */
void otp_now_iso(char *buf, int bufsize);

#endif /* OTP_PORTABLE_H */
